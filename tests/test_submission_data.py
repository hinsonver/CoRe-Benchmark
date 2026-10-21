"""Behavior-first checks for the submission companion installer."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[1]
ENTRY = HERE / 'tools/data.py'


class DataInstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.is_file(), 'new submission data entry is not implemented')
        spec = importlib.util.spec_from_file_location('submission_data', ENTRY)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='core-data-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'repo'
        (self.root / 'data/manifests').mkdir(parents=True)
        self.archive = self.base / 'history.zip'
        self.target = self.base / 'installed'
        self.payload = {'fixture/input.txt':b'input\n', 'fixture/scorer.py':b'# saved scorer\n'}
        self.files = {name:hashlib.sha256(data).hexdigest() for name,data in self.payload.items()}
        self.make_archive(self.payload)

    def make_archive(self, payload, *, extra=None, duplicate=False, symlink=False):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('BUNDLE.json', json.dumps({'schema_version':1,'files':self.files}))
            for name,data in payload.items():
                if symlink and name == next(iter(payload)):
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, data)
                else:
                    archive.writestr(name,data)
            if extra:
                archive.writestr(*extra)
            if duplicate:
                # Make a duplicate name without relying on a suppressed warning.
                with self.assertWarns(UserWarning):
                    archive.writestr('BUNDLE.json', '{}')
        metadata = {'schema_version':1,'historical':{
            'archive_filename':self.archive.name,
            'sha256':hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            'files':self.files,'file_count':len(self.files),
            'publication_status':'local_only_not_published'}}
        (self.root / 'data/manifests/SUBMISSION_DATA.json').write_text(json.dumps(metadata))

    def test_install_exact_archive_outside_repository(self):
        result = self.module.install(self.root, self.archive, self.target)
        self.assertEqual(result['files_verified'],2)
        for name,data in self.payload.items():
            self.assertEqual((self.target / name).read_bytes(),data)
        self.assertFalse(result['redistribution_authorized'])

    def test_wrong_archive_digest_fails_before_output(self):
        with self.archive.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'archive hash'):
            self.module.install(self.root,self.archive,self.target)
        self.assertFalse(self.target.exists())

    def test_member_hash_mismatch_fails(self):
        self.make_archive({**self.payload,'fixture/input.txt':b'changed'})
        with self.assertRaisesRegex(ValueError,'member hash'):
            self.module.install(self.root,self.archive,self.target)
        self.assertFalse(self.target.exists())

    def test_missing_member_fails(self):
        self.make_archive({'fixture/input.txt':b'input\n'})
        with self.assertRaisesRegex(ValueError,'members'):
            self.module.install(self.root,self.archive,self.target)
        self.assertFalse(self.target.exists())

    def test_extra_member_fails(self):
        self.make_archive(self.payload,extra=('other.txt',b'not declared'))
        with self.assertRaisesRegex(ValueError,'members'):
            self.module.install(self.root,self.archive,self.target)

    def test_traversal_member_fails(self):
        self.make_archive(self.payload,extra=('../escape.txt',b'not allowed'))
        with self.assertRaisesRegex(ValueError,'unsafe'):
            self.module.install(self.root,self.archive,self.target)
        self.assertFalse((self.base / 'escape.txt').exists())

    def test_symlink_member_fails(self):
        self.make_archive(self.payload,symlink=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            self.module.install(self.root,self.archive,self.target)

    def test_duplicate_member_fails(self):
        self.make_archive(self.payload,duplicate=True)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.module.install(self.root,self.archive,self.target)

    def test_existing_destination_preserved(self):
        self.target.mkdir()
        (self.target / 'keep.txt').write_text('user file')
        with self.assertRaises(FileExistsError):
            self.module.install(self.root,self.archive,self.target)
        self.assertEqual((self.target / 'keep.txt').read_text(),'user file')

    def test_destination_inside_repository_fails(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            self.module.install(self.root,self.archive,self.root / 'history')

    def test_destination_repository_itself_fails(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            self.module.install(self.root,self.archive,self.root)

    def test_status_does_not_claim_public_historical_download(self):
        result = self.module.status(self.root)
        self.assertEqual(result['historical']['publication_status'],'local_only_not_published')
        self.assertEqual(result['historical']['file_count'],2)
        self.assertFalse(result['model_calls'])

