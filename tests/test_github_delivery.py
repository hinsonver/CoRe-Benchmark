"""Fixed private-release acquisition contract; no network access is exercised."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.2.0-review-private-20261026'
ARCHIVE = 'CoRe-submission-VE-M01-M05-historical.zip'
DOWNLOAD = f'https://github.com/hinsonver/CoRe-Benchmark/releases/download/{TAG}/{ARCHIVE}'
SHA256 = '9569fe9d6d475ea0243b5d9a04f2a8ed098557873ffca7597cbcb6eef67bbc09'


class GitHubDeliveryContract(unittest.TestCase):
    def test_historical_manifest_has_fixed_same_repository_asset(self):
        historical = json.loads((ROOT / 'data/manifests/SUBMISSION_DATA.json').read_text())['historical']
        sources = json.loads((ROOT / 'data/manifests/CORE_SOURCES.json').read_text())
        self.assertEqual(historical.get('publication_status'), 'private_repository_asset')
        self.assertEqual(historical.get('release_tag'), TAG)
        self.assertEqual(historical.get('download_url'), DOWNLOAD)
        self.assertEqual(historical['archive_filename'], ARCHIVE)
        self.assertEqual(historical['sha256'], SHA256)
        self.assertEqual(historical['file_count'], 289)
        self.assertEqual(historical['files'], {**sources['private_files'], **sources['private_code']})

    def test_coverage_inventory_distinguishes_private_hosting_from_access(self):
        inventory = json.loads((ROOT / 'REPRODUCTION.json').read_text())
        material = inventory['historical_material']
        self.assertEqual(material.get('publication_status'), 'private_repository_asset')
        self.assertEqual(material.get('release_tag'), TAG)
        self.assertEqual(material.get('download_url'), DOWNLOAD)
        self.assertEqual(material['archive_sha256'], SHA256)
        self.assertEqual(material['bound_dependencies'], 264)
        self.assertEqual(material['bound_scoring_sources'], 25)
        self.assertEqual(inventory['readiness']['publication_status'], 'private_repository_prerelease')
        self.assertFalse(inventory['readiness']['actual_review_access_ready'])
        self.assertFalse(inventory['known_limits']['access']['reviewer_access_verified'])
        self.assertFalse(inventory['readiness']['exact_history_complete'])

    def test_authenticated_acquisition_and_existing_install_gate_are_documented(self):
        path = ROOT / 'docs/github-delivery.md'
        self.assertTrue(path.is_file(), 'fixed private GitHub acquisition guide is missing')
        text = path.read_text()
        for required in [DOWNLOAD, SHA256, 'gh auth login', 'gh auth status',
                         f'gh release download {TAG}', '--repo hinsonver/CoRe-Benchmark',
                         'CoRe-review-core-20261026.zip', 'SHA256SUMS', 'shasum -a 256 -c',
                         'python tools/data.py install', '--authorization-record',
                         'BUNDLE.json', '289', '264', '25', 'rights_basis', 'redistribution']:
            self.assertIn(required, text)

    def test_reader_navigation_does_not_describe_local_only_delivery(self):
        for name in ['README.md', 'docs/data.md', 'docs/reproduction.md',
                     'docs/limitations.md', 'docs/baseline-scoring.md']:
            text = (ROOT / name).read_text()
            self.assertIn('github-delivery.md', text, name)
            self.assertNotIn('separate local sibling archive', text.lower(), name)
        readme = (ROOT / 'README.md').read_text()
        self.assertIn('not released', readme)
        self.assertNotIn('LOCAL CORRECTED CANDIDATE', readme)
        licenses = (ROOT / 'LICENSES.md').read_text()
        self.assertIn('private Release asset', licenses)
        self.assertIn('default statistical core', licenses)


if __name__ == '__main__':
    unittest.main()
