import ast
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from word_document_generation_claim_audit import phrases
from word_document_generation_claim_audit.audit import audit, module_evidence, normalize, paragraphs, matches
from word_document_generation_claim_audit.__main__ import main

YES = '''word document generation
generate word document
generates word document
generating word document
generate word documents
generates word documents
generating word documents
create word document
creates word document
creating word document
create word documents
creates word documents
creating word documents
export word document
exports word document
exporting word document
export to word document
exports to word document
exporting to word document
export as word document
exports as word document
exporting as word document
word document export
word document exports
word document exporter
word document report generation
generate word document report
generates word document report
generating word document report
generate word document reports
create word document report
creates word document report
write word document
writes word document
writing word document
save as word document
saves as word document
save to word document
saves to word document
word document writer
word document writing
build word document
builds word document
building word document
generate docx
generates docx
generating docx
create docx
creates docx
creating docx'''.splitlines()
NO = '''no word document generation
does not generate word document
does not generate word documents
does not support word document generation
without word document generation
no word document export
does not export word document
does not export to word document
does not create word document
does not create word documents
no word document writer
does not write word document
does not save as word document
no word document report generation
does not generate word document reports
does not build word document
does not generate docx
does not create docx
word document generation not supported
no word document generation support
without word document export
does not support word document export
no word document exporter
does not generate word document report'''.splitlines()
GENERIC = '''generate_word_document generate_word_documents create_word_document create_word_documents export_word_document export_to_word_document export_as_word_document write_word_document save_word_document save_as_word_document build_word_document render_word_document make_word_document generate_docx create_docx export_docx export_to_docx write_docx save_docx build_docx generate_docx_document create_docx_document export_docx_document write_docx_document'''.split()
GOOD = 'from docx import Document\nx = Document()\nx.save("out.docx")'


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, path, text):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)

    def result(self, source=GOOD, claim='generate word document', filename='app.py', **kwargs):
        self.put('README.md', claim)
        if source is not None:
            self.put(filename, source)
        return audit(self.root, **kwargs)

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            try:
                code = main(list(args))
            except SystemExit as error:
                code = error.code
        return code, out.getvalue()

    def test_phrase_oracle(self):
        tree = ast.parse(Path(phrases.__file__).read_text())
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)}
        for key, expected, count in [('WORDDOCUMENTGENERATION', YES, 50), ('NOWORDDOCUMENTGENERATION', NO, 24), ('GENERIC_NAMES', GENERIC, 24)]:
            self.assertEqual(tuple(expected), values[key])
            self.assertEqual(count, len(set(values[key])))

    def test_pass(self):
        self.assertEqual('PASS', self.result()['verdict'])

    def test_bad_exact_cli(self):
        self.result('x=1')
        code, out = self.cli('audit', str(self.root), '--json')
        self.assertEqual(2, code)
        finding = json.loads(out)['findings'][0]
        self.assertEqual('documented-word-document-generation-claim-false', finding['rule'])
        self.assertEqual('HIGH', finding['severity'])
        self.assertTrue(finding['message'])

    def test_denial(self):
        result = self.result(claim=NO[0])
        self.assertEqual('documented-no-word-document-generation-claim-false', result['findings'][0]['rule'])
        self.assertEqual('HIGH', result['findings'][0]['severity'])
        self.assertEqual(2, self.cli('audit', str(self.root))[0])

    def test_test_only(self):
        result = self.result(filename='tests/check.py')
        self.assertEqual('MEDIUM', result['findings'][0]['severity'])
        self.assertEqual(0, self.cli('audit', str(self.root))[0])
        self.assertEqual(2, self.cli('audit', str(self.root), '--fail-on', 'medium')[0])

    def test_no_source_asymmetry(self):
        self.assertEqual('FAIL', self.result(None)['verdict'])
        self.assertEqual('PASS', self.result(None, NO[0])['verdict'])

    def test_no_claim(self):
        self.assertEqual('PASS', self.result(claim='Read documents')['verdict'])

    def test_fences(self):
        for marker in ('```', '~~~', '   ````'):
            self.assertEqual('PASS', self.result('', marker+'\ngenerate docx\n'+marker)['verdict'])
        self.assertEqual('FAIL', self.result('', '`generate docx`')['verdict'])

    def test_fence_closure(self):
        self.assertEqual([], paragraphs('````\ngenerate docx\n```\ngenerate docx'))
        self.assertEqual(['generate docx'], paragraphs('~~~\nx\n~~~\ngenerate docx'))

    def test_normalization(self):
        self.assertEqual('does not generate word document', normalize("DOESN’T generate-word\n document"))
        self.assertEqual('PASS', self.result('', "doesn't generate-word-document")['verdict'])
        self.assertEqual('PASS', self.result('', 'regenerate docxify')['verdict'])

    def test_longest_first(self):
        found, _ = matches('generate word document reports', YES)
        self.assertEqual(['generate word document reports'], found)
        found, _ = matches('a b c', ('b c', 'a b'))
        self.assertEqual(['a b'], found)

    def test_split_modules(self):
        self.put('writer.py', 'x.save("a.docx")')
        self.assertEqual('FAIL', self.result('from docx import Document\nx=Document()')['verdict'])

    def test_doc_paths(self):
        self.put('nested/docs/guide.md', 'generate docx')
        self.assertEqual('FAIL', audit(self.root)['verdict'])
        self.assertEqual('PASS', audit(self.root, ignore=['nested'])['verdict'])

    def test_symlinks(self):
        self.put('README.md', 'generate docx')
        self.put('fixtures/real.py', GOOD)
        (self.root/'linked.py').symlink_to(self.root/'fixtures/real.py')
        (self.root/'linked').symlink_to(self.root/'fixtures', target_is_directory=True)
        self.assertEqual('FAIL', audit(self.root)['verdict'])

    def test_ignore_repeatable(self):
        self.result(filename='vendor/a.py')
        self.put('generated/b.py', GOOD)
        self.assertEqual(2, self.cli('audit', str(self.root), '--ignore', 'vendor', '--ignore', 'generated')[0])

    def test_usage_errors(self):
        for args in [[], ['wrong'], ['audit', '/missing-r222'], ['audit', '--fail-on', 'HIGH'], ['audit', '--ignore'], ['audit', '.', '--ignore', 'a', 'b']]:
            self.assertEqual(1, self.cli(*args)[0])

    def test_io_error(self):
        self.put('README.md', 'generate docx')
        (self.root/'app.py').write_bytes(b'\xff')
        self.assertEqual(1, self.cli('audit', str(self.root))[0])

    def test_default_repo_verbose(self):
        self.result()
        code, out = self.cli('audit', str(self.root), '--verbose')
        self.assertEqual(0, code)
        self.assertIn('production_evidence', out)

    def test_version_entry_point(self):
        self.assertEqual((0, '0.1.0\n'), self.cli('--version'))
        run = subprocess.run([sys.executable, '-m', 'word_document_generation_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual(0, run.returncode)
        self.assertEqual('0.1.0\n', run.stdout)

    def test_readme_self_audit(self):
        root = Path(__file__).resolve().parents[1]
        if (root/'README.md').exists():
            result = audit(root, ignore=['.verification', 'build', 'dist'])
            self.assertEqual([], result['claims'])
            self.assertEqual([], result['denials'])
            self.assertEqual('PASS', result['verdict'])


def evidence_test(source, expected):
    def test(self):
        self.assertEqual(expected, bool(module_evidence(source)), source)
    return test

for library, constructor in [('docx', 'Document'), ('docxtpl', 'DocxTemplate')]:
    sources = [
        'from {0} import {1}\nx={1}()\nx.save("a.docx")',
        'import {0}\nx={0}.{1}()\nx.save("a.docx")',
        'import {0} as lib\nx=lib.{1}()\nx.save("a.docx")',
        'from {0} import {1} as Factory\nx=Factory()\nx.save("a.docx")',
        'import {0}\nx={0}.nested.{1}()\nother.save("a")',
        'from {0}.{2} import {1}\nx={1}()\nx.render({{}})\nx.save("a")',
        'import {0}.{2} as lib\nx=lib.{1}()\nx.save("a")',
    ]
    for i, source in enumerate(sources):
        setattr(AuditTests, 'test_route_'+library+'_'+str(i), evidence_test(source.format(library, constructor, 'api' if library=='docx' else 'template'), True))
    negatives = [
        'import {0}', 'from {0} import {1}\nx={1}()',
        'from {0} import {1}\nx={1}("existing.docx")',
        'from {0} import {1}\ndef {1}(): pass\nx={1}()\nx.save("a")',
        'import {0} as lib\nlib=other\nlib.{1}()\nx.save("a")',
        'from {0} import {1} as F\nF: object=other\nF()\nx.save("a")',
        'import {0} as lib\nwith thing as lib:\n lib.{1}()\n x.save("a")',
        'from {0} import {1}\nclass {1}: pass\n{1}()\nx.save("a")',
    ]
    for i, source in enumerate(negatives):
        setattr(AuditTests, 'test_rejected_'+library+'_'+str(i), evidence_test(source.format(library, constructor), False))

for name in GENERIC:
    for i, source in enumerate(['x.{0}()', 'from tool import {0}\n{0}()', 'from tool import {0} as f\nf()', 'import tool.{0} as f\nf()']):
        setattr(AuditTests, 'test_generic_'+name+'_'+str(i), evidence_test(source.format(name), True))
    for i, source in enumerate(['{0}()', 'x.{0}', 'def {0}(): pass\nx.{0}()', 'from tool import {0} as f\nf=other\nf()', 'class C:\n def {0}(self): pass\nx.{0}()']):
        setattr(AuditTests, 'test_generic_negative_'+name+'_'+str(i), evidence_test(source.format(name), False))

NOT_EVIDENCE = [
    'import mammoth', 'import pypandoc', 'mammoth.convert_to_html(f)', 'mammoth.convert_to_markdown(f)',
    'docx2txt.process(f)', 'pypandoc.convert_text(s, "docx")', 'pypandoc.convert_file(f, "docx")',
    'import aspose.words as aw\nx=aw.Document()\nx.save("a.docx")',
    'from docxcompose.composer import Composer\nx=Composer(d)\nx.save("a.docx")',
    'subprocess.run(["libreoffice", "a.docx"])', 'subprocess.run(["pandoc", "a.docx"])',
    'open("a.txt", "w").write("a")', 'Path("a.md").write_text("a")', 'Image.new("RGB", (1,1)).save("a.png")',
    'from reportlab.pdfgen.canvas import Canvas\nx=Canvas("a.pdf")\nx.save()',
    'from fpdf import FPDF\nx=FPDF()\nx.output("a.pdf")', 'WeasyPrint.HTML("a").write_pdf("a.pdf")', 'pypdf.PdfWriter().write("a.pdf")',
    'from openpyxl import Workbook\nx=Workbook()\nx.save("a.xlsx")', 'pandas.DataFrame().to_excel("a.xlsx")',
    'xlsxwriter.Workbook("a.xlsx").close()', '"word document docx Word"',
    'mindee.parse(InvoiceV4, f)', 'azure.begin_analyze_document("prebuilt-layout", f)', 'veryfi.Client()',
    'documentai.process_document(request=r)', 'textract.analyze_document(Document=d)', 'eden.universal_ai(model=m)',
    'LlamaParse().load_data(f)', 'nanonets.OCR(model_id=m)', 'docsumo.upload(f)',
    'abbyy.process(skill_id=s)', 'rossum.upload(queue=q)', 'klippa.parse(f)', 'parseur.upload(f)', 'extend.run(workflow=w)',
    '# generate_word_document()\nx="generate docx"', 'def invalid(',
]
for i, source in enumerate(NOT_EVIDENCE):
    setattr(AuditTests, 'test_not_evidence_'+str(i), evidence_test(source, False))

for i, phrase in enumerate(YES):
    def test(self, phrase=phrase):
        self.assertEqual('FAIL', self.result('', phrase)['verdict'])
    setattr(AuditTests, 'test_positive_phrase_'+str(i), test)
for i, phrase in enumerate(NO):
    def test(self, phrase=phrase):
        result = self.result('', phrase)
        self.assertEqual([], result['claims'])
        self.assertEqual(1, len(result['denials']))
        self.assertEqual('PASS', result['verdict'])
    setattr(AuditTests, 'test_negative_phrase_'+str(i), test)
for i, path in enumerate(['tests/a.py', 'nested/tests/a.py', 'test_app.py', 'app_test.py', 'fixtures/a.py', 'docs/a.py', 'examples/a.py']):
    def test(self, path=path):
        result = self.result(filename=path)
        self.assertEqual([], result['production_evidence'])
        self.assertEqual(bool('tests' in Path(path).parts or Path(path).name.startswith('test_') or Path(path).name.endswith('_test.py')), bool(result['test_evidence']))
    setattr(AuditTests, 'test_excluded_path_'+str(i), test)

if __name__ == '__main__':
    unittest.main()
