"""Read-only documentation and AST pattern audit."""
import ast
import os
import re
from pathlib import Path

from .phrases import WORDDOCUMENTGENERATION, NOWORDDOCUMENTGENERATION, GENERIC_NAMES

POSITIVE_RULE = 'documented-word-document-generation-claim-false'
NEGATIVE_RULE = 'documented-no-word-document-generation-claim-false'


def normalize(text):
    return ' '.join(text.lower().replace('’', "'").replace("n't", ' not').replace('-', ' ').split())


def matches(text, phrases):
    """Consume longest matches first, preserving word boundaries."""
    found = []
    for phrase in sorted(phrases, key=lambda value: (-len(value), value)):
        pattern = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
        if re.search(pattern, text):
            found.append(phrase)
            text = re.sub(pattern, lambda m: ' ' * len(m.group()), text)
    return found, text


def paragraphs(text):
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
                lines.append('')
            continue
        if marker and (marker[1][0] != '`' or '`' not in marker[2]):
            fence = marker[1]
            lines.append('')
        else:
            lines.append(line)
    return [normalize(p) for p in re.split(r'\n\s*\n', '\n'.join(lines)) if p.strip()]


def module_evidence(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    imports = {}
    blocked = set()
    definitions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module or '') + '.' + alias.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.add(node.name)
            blocked.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.With, ast.AsyncWith)):
            targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AnnAssign) else [i.optional_vars for i in node.items])
            for target in targets:
                if target is not None:
                    blocked.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    def resolved(func):
        if isinstance(func, ast.Name) and func.id not in blocked:
            return imports.get(func.id, '')
        return ''
    calls = [n.func for n in ast.walk(tree) if isinstance(n, ast.Call)]
    save = any(isinstance(f, ast.Attribute) and f.attr == 'save' for f in calls)
    evidence = set()
    for func in calls:
        full = resolved(func)
        name = func.attr if isinstance(func, ast.Attribute) else full.rsplit('.', 1)[-1]
        if name in GENERIC_NAMES and name not in definitions:
            evidence.add(name)
        if not save:
            continue
        for library, constructor in (('docx', 'Document'), ('docxtpl', 'DocxTemplate')):
            if constructor in definitions:
                continue
            valid = full.startswith(library + '.') and full.rsplit('.', 1)[-1] == constructor
            if isinstance(func, ast.Attribute) and func.attr == constructor:
                base = func.value
                while isinstance(base, ast.Attribute):
                    base = base.value
                valid = isinstance(base, ast.Name) and base.id not in blocked and imports.get(base.id, '').split('.')[0] == library
            if valid:
                evidence.add(library + '.' + constructor + '+save')
    return sorted(evidence)


def audit(repo='.', ignore=(), fail_on='high'):
    root = Path(repo)
    if not root.is_dir() or root.is_symlink():
        raise OSError('Repository must be a readable directory: ' + str(root))
    claims, denials, production, tests = [], [], [], []
    prefixes = [p.replace('\\', '/').removeprefix('./').rstrip('/') for p in ignore]
    def walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for filename in sorted(files):
            path = Path(directory) / filename
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or any(rel.startswith(p) for p in prefixes):
                continue
            parts = path.relative_to(root).parts
            if rel == 'README.md' or (path.suffix == '.md' and 'docs' in parts[:-1]):
                for paragraph in paragraphs(path.read_text(encoding='utf-8')):
                    negative, remaining = matches(paragraph, NOWORDDOCUMENTGENERATION)
                    positive, _ = matches(remaining, WORDDOCUMENTGENERATION)
                    denials.extend({'path': rel, 'phrase': p} for p in negative)
                    claims.extend({'path': rel, 'phrase': p} for p in positive)
            if path.suffix != '.py' or any(p in ('fixtures', 'docs', 'examples') for p in parts[:-1]):
                continue
            evidence = module_evidence(path.read_text(encoding='utf-8'))
            destination = tests if 'tests' in parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py') else production
            destination.extend({'path': rel, 'route': route} for route in evidence)
    findings = []
    if claims and not production:
        findings.append({'rule': POSITIVE_RULE, 'severity': 'MEDIUM' if tests else 'HIGH', 'message': 'The documented capability has only test evidence.' if tests else 'The documented capability has no production evidence.', 'locations': sorted({c['path'] for c in claims})})
    if denials and production:
        findings.append({'rule': NEGATIVE_RULE, 'severity': 'HIGH', 'message': 'The documented denial conflicts with production evidence.', 'locations': sorted({d['path'] for d in denials})})
    failed = any(f['severity'] == 'HIGH' or fail_on == 'medium' for f in findings)
    return {'verdict': 'FAIL' if failed else 'PASS', 'findings': findings, 'claims': claims, 'denials': denials, 'production_evidence': production, 'test_evidence': tests}
