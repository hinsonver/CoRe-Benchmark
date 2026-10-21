"""Reader-facing contract of the new local submission repository."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SubmissionContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ROOT.is_dir(),'new submission repository has not been assembled')

    def test_ordered_citation(self):
        citation = (ROOT / 'CITATION.cff').read_text()
        self.assertLess(citation.index('family-names: Yang'),citation.index('family-names: Chen'))
        self.assertLess(citation.index('family-names: Chen'),citation.index('family-names: Fan'))
        for email in ['okiyang@muc.edu.cn','202301050@muc.edu.cn','fanj@ruc.edu.cn']:
            self.assertIn(email,citation)
        self.assertNotIn('doi:',citation)

    def test_complete_paper_float_navigation(self):
        mapping = json.loads((ROOT / 'paper/result-map.json').read_text())
        self.assertEqual(mapping['body_pages'],12)
        self.assertEqual(mapping['total_pages'],14)
        records = mapping['entries']
        self.assertEqual(sum(r['kind']=='figure' for r in records),7)
        self.assertEqual(sum(r['kind']=='table' for r in records),18)
        for record in records:
            self.assertTrue((ROOT / record['manuscript_source']).is_file(),record['label'])
            for name in record['asset_paths']+record['csv_paths']:
                self.assertTrue((ROOT / name).is_file(),name)
            if record['reference_table']:
                self.assertTrue((ROOT / record['reference_table']).is_file())

    def test_current_tables_and_csvs(self):
        self.assertEqual(len(list((ROOT / 'results/tables').glob('*.tex'))),19)
        self.assertEqual(len(list((ROOT / 'results/figures').glob('*.csv'))),9)
        config = json.loads((ROOT / 'code/config/paper_presentation.json').read_text())
        self.assertEqual(len(config['sources']),17)

    def test_movie_materials_separate_and_bound(self):
        sources = json.loads((ROOT / 'data/manifests/CORE_SOURCES.json').read_text())
        metadata = json.loads((ROOT / 'data/manifests/SUBMISSION_DATA.json').read_text())
        self.assertEqual(metadata['historical']['file_count'],427)
        self.assertEqual(metadata['historical']['publication_status'],'local_only_not_published')
        self.assertEqual(metadata['historical']['files'],{**sources['private_files'],**sources['private_code']})
        for name in sources['omitted_files']:
            self.assertFalse((ROOT / name).exists(),name)

    def test_reader_entries_and_companions(self):
        for name in ['README.md','docs/data.md','docs/reproduction.md','docs/results.md',
                     'docs/limitations.md','tools/data.py','tools/core.py','tools/check_rayyan.py',
                     'paper/companions/README.md','paper/frozen-claims.md','paper/latex/main.pdf']:
            self.assertTrue((ROOT / name).is_file(),name)
        self.assertEqual(len(list((ROOT / 'paper/companions').glob('[0-9][0-9]-*.md'))),6)
        replay_requirements = (ROOT / 'environment/requirements-replay.txt').read_text()
        self.assertNotIn('openai',replay_requirements)
        for path in (ROOT / 'scripts').glob('*.sh'):
            self.assertTrue(path.stat().st_mode & 0o111, str(path)+' must be executable')

    def test_no_publication_assertion_or_approval(self):
        self.assertIn('not released',(ROOT / 'README.md').read_text())
        self.assertFalse((ROOT / 'release-approval.json').exists())

    def test_new_markdown_links_resolve(self):
        files = [ROOT / 'README.md',ROOT / 'paper/claim-map.md']
        files += list((ROOT / 'docs').glob('*.md'))
        files += list((ROOT / 'paper/companions').glob('*.md'))
        for path in files:
            for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^)]+)\)',path.read_text()):
                link = match.group(1).split('#',1)[0]
                if not link or '://' in link or link.startswith('mailto:'):
                    continue
                target = (path.parent / link).resolve()
                self.assertTrue(target.exists(),f'{path.relative_to(ROOT)} -> {link}')

    def test_latex_local_href_targets_resolve(self):
        source = ROOT / 'paper/latex/main.tex'
        local = []
        for link in re.findall(r'\\href\{([^}]+)\}',source.read_text()):
            if '://' not in link and not link.startswith('mailto:') and '\\' not in link:
                local.append(link)
                self.assertTrue((source.parent / link).resolve().is_file(),link)
        self.assertIn('../CoRe-companion-index.md',local)


if __name__ == '__main__':
    unittest.main()
