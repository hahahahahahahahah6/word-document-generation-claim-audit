# Documentation claim auditor

An offline static auditor comparing documentation promises with listed source patterns. It reads root README.md and Markdown under any docs path component. Source is parsed with the standard library, never executed. Audits perform no network access, telemetry or writes.

## Usage

```sh
PIP_NO_INDEX=1 python3 -m pip install --no-index .
word-document-generation-claim-audit audit . --json
python3 -m word_document_generation_claim_audit audit . --verbose
word-document-generation-claim-audit audit . --fail-on medium --ignore vendor --ignore generated
word-document-generation-claim-audit --version
```

The audit subcommand defaults to the current directory. Each ignore option accepts one relative path prefix. The default threshold is high; medium also fails on test-only findings. Exit codes are 0 for PASS, 2 for findings meeting the threshold, and 1 for usage or I/O errors. PASS can contain a medium finding. JSON includes verdict, findings (rule, severity, message, locations), production_evidence, test_evidence, claims and denials.

## Matching

Blank lines delimit paragraphs. Backtick and tilde fences with up to three leading spaces are excluded; inline code counts. Text is lowercased, contractions expanded, hyphens replaced with spaces and whitespace collapsed. Exact phrases match at word boundaries, longest first with alphabetical ties. Denial spans are removed before positive matching. Each family produces at most one finding.

Imports and aliases resolve; local function, method and class definitions shadow route names. Assignments, annotated assignments and context-manager bindings shadow imported names. Syntax-invalid files and symlinks provide no evidence. Files under fixtures, docs and examples are excluded; tests are tracked separately. A positive statement without source fails; a denial without source passes.

```text
documented-word-document-generation-claim-false HIGH (MEDIUM for test-only evidence)
documented-no-word-document-generation-claim-false HIGH
```

## Evidence and vocabulary

The checked operation produces .docx files from code or data, including paragraphs, headings, tables and runs. The precise vocabulary and accepted calls follow.

```text
word document generation
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
creating docx
no word document generation
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
does not generate word document report

Generic calls:
generate_word_document, generate_word_documents, create_word_document, create_word_documents, export_word_document, export_to_word_document, export_as_word_document, write_word_document, save_word_document, save_as_word_document, build_word_document, render_word_document, make_word_document, generate_docx, create_docx, export_docx, export_to_docx, write_docx, save_docx, build_docx, generate_docx_document, create_docx_document, export_docx_document, write_docx_document

docx.Document() + any .save() call in the same module
docxtpl.DocxTemplate() + any .save() call in the same module

Each pair requires a single module. Object identity and execution order are
not checked. Generic Attribute calls accept any base; bare Names need an
import. No third-party runtime dependency is required.
```

## Honest limitations

Static patterns are not semantic proof. Dead code counts. Unresolved alias chains are missed. Exact wording and the denial vocabulary limit coverage. Detailed limitations follow in a fenced block to avoid making claims about this auditor.

```text
- The bare phrases "word document generation" / "generate word
  document" / "create word document" / "export word document" are
  deliberately WORDDOCUMENTGENERATION phrases: in document-tool docs
  they almost always name Word document generation. But "create word
  document" can also name creating an empty .docx shell with no
  content, and "export word document" can name a menu item that
  merely downloads an already-generated document: a doc that means
  download, not generation, is a false positive; the tool flags the
  claim, only the code decides.
- "word document report" phrases ("word document report generation",
  "generate word document report", "create word document report") are
  deliberately phrases: a doc can say "word document report" about a
  report that happens to be delivered as a Word document generated
  elsewhere, with no generation code in the repo. The tool flags
  the claim; only the code decides.
- "generate docx" / "create docx" phrases are deliberately phrases:
  a doc can say "generate docx" about a tool that shells out to
  LibreOffice or pandoc, which the tool deliberately does NOT detect
  (subprocess is NOT evidence). The tool flags the claim; only the
  code decides — and a subprocess-only codebase will be flagged
  HIGH, by design.
- "save as word document" / "save to word document" are deliberately
  phrases: a doc can say "save as word document" about a print
  dialog's save option in a GUI, with no Word-writing code in the
  repo. The tool flags the claim; only the code decides.
- "word document writer" / "word document writing" are deliberately
  phrases: "word document writer" can also name a class that only
  wraps a Word document reader, or a job title in prose. The tool
  flags the claim; only the code decides.
- "build word document" / "building word document" are deliberately
  phrases: a doc can say "build word document" about a build step
  that assembles a document from already-rendered parts, or about
  building the tool itself. The tool flags the claim; only the code
  decides.
- A python-docx Document construction with no .save() in the module
  is NOT detected: constructing a document without saving writes no
  file. Say so in the README.
- A DocxTemplate construction with no .save() in the module is NOT
  detected. Say so in the README.
- A DocxTemplate construction with .save() but no .render() IS
  detected: save() writes the file even if the template was never
  rendered. Say so in the README.
- A python-docx Document opened from an existing file with no .save()
  in the module is NOT detected: that is reading, not generation.
  Say so in the README.
- mammoth convert_to_html / convert_to_markdown and docx2txt.process
  are NOT detected: reading a Word document is not generating one.
  Say so in the README.
- pypandoc convert_text / convert_file are NOT detected: shelling out
  to pandoc is NOT evidence by design. Say so in the README.
- aspose-words Document + .save() calls are NOT detected: they are
  not a listed route this round (commercial library, wheel not
  inspected). Say so in the README.
- docxcompose Composer + .save() calls are NOT detected: they are
  not a listed route this round (composition merges existing
  documents). Say so in the README.
- LibreOffice / UNO / pandoc subprocess calls are NOT detected:
  shelling out to an external binary is NOT evidence by design. Say
  so in the README.
- Saving .txt / .html / .md / image files is NOT detected: writing a
  non-Word file is not generating a Word document. Say so in the
  README.
- reportlab / fpdf / WeasyPrint / pypdf PDF writes are NOT detected:
  writing a PDF is not generating a Word document. Say so in the
  README.
- openpyxl / xlsxwriter / pandas to_excel writes are NOT detected:
  writing a spreadsheet is not generating a Word document. Say so in
  the README.
- Mindee parse with ANY product is NOT detected: mindee extracts
  from documents; it never writes Word documents. Say so in the
  README.
- Azure begin_analyze_document with ANY model id is NOT detected:
  Document Intelligence reads documents; it has no Word document
  generation operation. Say so in the README.
- Veryfi calls of ANY kind are NOT detected: veryfi extracts fields
  from documents; it has no Word document generation method. Say so
  in the README.
- Google Document AI process_document / batch_process_documents
  with ANY processor is NOT detected: Document AI has no Word
  document generation processor. Say so in the README.
- Eden AI universal-ai calls with ANY model id are NOT detected:
  Eden AI documents no Word document generation model. Say so in the
  README.
- Textract calls of ANY kind are NOT detected: Textract reads
  documents; it has no Word document generation operation. Say so in
  the README.
- LlamaParse calls are NOT detected: its parsing API reads
  documents; it has no Word document generation operation. Say so in
  the README.
- Nanonets / Docsumo / ABBYY Vantage / Rossum / Klippa / Parseur /
  Extend calls are NOT detected: opaque model / skill / queue /
  template / workflow IDs, or a generic upload endpoint with the
  document type configured outside the call — all extraction-side,
  no fixed fingerprint. Say so in the README.
- A hand-rolled Word writer built on raw OOXML / ZIP XML assembly
  (writing .docx bytes by hand, no listed call) is NOT detected: the
  tool requires a listed call. Say so in the README.
- PDF generation claims ("generate pdf", "pdf generation"),
  spreadsheet generation claims ("generate spreadsheet",
  "spreadsheet generation"), invoice extraction claims ("extract
  invoices", "invoice extraction"), receipt extraction claims
  ("extract receipts", "receipt extraction"), ID document extraction
  claims ("extract passports", "passport extraction"), bank check
  extraction claims ("extract bank checks", "check extraction"),
  bank statement extraction claims ("extract bank statements",
  "statement extraction"), tax form extraction claims ("extract tax
  forms", "extract w2 forms", "1099 extraction"), pay stub
  extraction claims ("extract pay stubs", "payslip extraction"),
  health insurance card extraction claims ("extract health insurance
  cards", "health insurance card extraction"), business card
  extraction claims ("extract business cards", "business card
  extraction"), credit card extraction claims ("extract credit
  cards", "credit card extraction"), contract extraction claims
  ("extract contracts", "contract extraction"), mortgage extraction
  claims ("extract mortgages", "mortgage extraction"), resume
  extraction claims ("extract resumes", "resume extraction"), bill of
  lading extraction claims ("extract bills of lading", "bill of
  lading extraction"), delivery note extraction claims ("extract
  delivery notes", "delivery note extraction"), carte grise
  extraction claims ("extract carte grises", "carte grise
  extraction"), energy bill extraction claims ("extract energy
  bills", "energy bill extraction"), marriage certificate extraction
  claims ("extract marriage certificates", "marriage certificate
  extraction"), bank account details extraction claims ("extract
  bank account details", "bank account details extraction"),
  nutrition facts label extraction claims ("extract nutrition facts
  labels", "nutrition facts label extraction"), material certificate
  extraction claims ("extract material certificates", "material
  certificate extraction"), US mail extraction claims ("extract us
  mail", "us mail extraction"), invoice splitter claims ("split
  invoices", "invoice splitting"), multi-receipts detection claims
  ("detect multiple receipts", "multi receipt detection"), French
  health card extraction claims ("extract carte vitales", "french
  health card extraction"), Indian passport extraction claims
  ("extract indian passports", "indian passport extraction"), driver
  license extraction claims ("extract driver licenses", "driver
  license extraction"), vaccination card extraction claims ("extract
  vaccination cards", "vaccination card extraction"), document
  cropping claims ("crop documents", "document cropping"), and
  spreadsheet generation claims ("generate spreadsheet",
  "spreadsheet generation") are NOT in the phrase lists: this family
  covers Word document generation only. Say so in the README.
- As with every family: static pattern matching, not semantic
  judgement; dead code counts; alias chains the tracer cannot follow
  are missed; exact phrases only, not semantics; denial handling
  depends on the denial phrase list; each route must sit in a single
  module.

```

## Development

```sh
python3 -m unittest discover
PIP_NO_INDEX=1 python3 -m build
```

Requires interpreter version 3.9 or later. Distributed under the MIT license.
