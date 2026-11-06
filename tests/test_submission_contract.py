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
        authors = re.findall(r'family-names: (\w+)', citation.split('\npreferred-citation:',1)[0])
        self.assertEqual(authors, ['Yang', 'Zhang', 'Mi', 'Fan', 'Chen', 'Du'])
        self.assertIn('Knowledge Dependence in LLM-based Data Cleaning', citation)
        for email in ['okiyang@muc.edu.cn','26302276@muc.edu.cn','25012086@muc.edu.cn','fanj@ruc.edu.cn',
                      '202301050@muc.edu.cn','duyong@ruc.edu.cn']:
            self.assertIn(email,citation)
        self.assertNotIn('doi:',citation)

    def test_six_authors_and_sole_correspondence(self):
        source=(ROOT/'paper/latex/main.tex').read_text()
        self.assertEqual(re.findall(r'\\author\{([^}]+)\}',source),
                         ['Jingru Yang','Honglu Zhang','Jiayi Mi','Ju Fan','Zheng Chen','Xiaoyong Du'])
        self.assertIn(r'\author{Zheng Chen}'+'\n'+r'\authornote{Zheng Chen is the corresponding author.}',source)
        self.assertEqual(source.count(r'\authornote{'),1)
        self.assertNotIn(r'\authornotemark',source)
        self.assertIn(r'\email{25012086@muc.edu.cn}',source)
        self.assertIn(r'\settopmatter{authorsperrow=3}',source)

    def test_report_and_binding_correspondence(self):
        source=(ROOT/'paper/companions/CoRe-Supplementary-Technical-Report.tex').read_text()
        self.assertIn(r'Jiayi Mi\textsuperscript{1}',source)
        self.assertIn(r'Ju Fan\textsuperscript{2}',source)
        self.assertNotIn(r'Ju Fan\textsuperscript{2,*}',source)
        self.assertIn(r'Zheng Chen\textsuperscript{1,*}',source)
        binding=json.loads((ROOT/'paper/revision-binding.json').read_text())['current_adoption']
        self.assertEqual(binding['authors'],['Jingru Yang','Honglu Zhang','Jiayi Mi','Ju Fan','Zheng Chen','Xiaoyong Du'])
        self.assertEqual(binding['corresponding_authors'],[{'name':'Zheng Chen','email':'202301050@muc.edu.cn'}])
        self.assertIn('Corresponding author: Zheng Chen',source)
        self.assertNotIn('Corresponding authors:',source)

    def test_complete_paper_float_navigation(self):
        mapping = json.loads((ROOT / 'paper/result-map.json').read_text())
        self.assertEqual(mapping['body_pages'],12)
        self.assertEqual(mapping['total_pages'],14)
        records = mapping['entries']
        self.assertEqual(sum(r['kind']=='figure' for r in records),8)
        self.assertEqual(sum(r['kind']=='table' for r in records),17)
        for record in records:
            self.assertTrue((ROOT / record['manuscript_source']).is_file(),record['label'])
            for name in record['asset_paths']+record['csv_paths']:
                self.assertTrue((ROOT / name).is_file(),name)
            if record['reference_table']:
                self.assertTrue((ROOT / record['reference_table']).is_file())

    def test_current_tables_and_csvs(self):
        self.assertEqual(len(list((ROOT / 'results/tables').glob('*.tex'))),19)
        self.assertEqual(len(list((ROOT / 'results/figures').glob('*.csv'))),11)
        config = json.loads((ROOT / 'code/config/paper_presentation.json').read_text())
        self.assertEqual(len(config['sources']),17)

    def test_movie_materials_separate_and_bound(self):
        sources = json.loads((ROOT / 'data/manifests/CORE_SOURCES.json').read_text())
        metadata = json.loads((ROOT / 'data/manifests/SUBMISSION_DATA.json').read_text())
        self.assertEqual(metadata['historical']['file_count'],289)
        self.assertEqual(metadata['historical']['publication_status'],'public_repository_asset')
        self.assertEqual(metadata['historical']['files'],{**sources['private_files'],**sources['private_code']})
        for name in sources['omitted_files']:
            self.assertFalse((ROOT / name).exists(),name)

    def test_reader_entries_and_companions(self):
        for name in ['README.md','docs/data.md','docs/reproduction.md','docs/results.md',
                     'docs/limitations.md','tools/data.py','tools/core.py','tools/check_rayyan.py',
                     'paper/companions/README.md','paper/frozen-claims.md','paper/latex/main.pdf']:
            self.assertTrue((ROOT / name).is_file(),name)
        self.assertEqual(len(list((ROOT / 'paper/companions').glob('[0-9][0-9]-*.md'))),0)
        self.assertTrue((ROOT / 'paper/CoRe-Supplementary-Technical-Report.pdf').is_file())
        replay_requirements = (ROOT / 'environment/requirements-replay.txt').read_text()
        self.assertNotIn('openai',replay_requirements)
        for path in (ROOT / 'scripts').glob('*.sh'):
            self.assertTrue(path.stat().st_mode & 0o111, str(path)+' must be executable')

    def test_public_repository_links_the_verified_arxiv_preprint(self):
        readme=(ROOT / 'README.md').read_text()
        self.assertIn('Public research repository',readme)
        self.assertIn('https://arxiv.org/abs/2611.08106',readme)
        self.assertNotIn('awaiting moderation',readme)
        citation=(ROOT / 'CITATION.cff').read_text().split('\npreferred-citation:',1)[1]
        self.assertEqual(re.findall(r'family-names: (\w+)',citation),
                         ['Yang','Zhang','Mi','Fan','Chen','Du'])
        self.assertIn('value: "arXiv:2611.08106"',citation)
        self.assertIn('journal: arXiv',citation)
        self.assertIn('https://arxiv.org/abs/2611.08106',citation)
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
        text = source.read_text()
        self.assertIn('https://github.com/hinsonver/CoRe-Benchmark/raw/refs/heads/main/paper/CoRe-Supplementary-Technical-Report.pdf', text)
        self.assertIn(r'\#nameddest=companion-#1', text)


if __name__ == '__main__':
    unittest.main()
