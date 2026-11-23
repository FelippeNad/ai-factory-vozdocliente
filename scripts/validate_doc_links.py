"""Valida links relativos e ancoras da documentacao, sem acessar a rede."""
import html
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class HtmlLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and name in ('href', 'src'):
                self.links.append(value)
            if value and (name == 'id' or (tag == 'a' and name == 'name')):
                self.anchors.add(value)


def without_fences(text):
    output, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
        elif fence is None:
            output.append(line)
    return '\n'.join(output)


def markdown_anchors(text):
    anchors, counts = set(), {}
    for line in without_fences(text).splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if not match:
            continue
        title = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', match[1])
        title = html.unescape(re.sub(r'<[^>]*>', '', title)).lower()
        slug = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        anchors.add(slug + (f'-{number}' if number else ''))
    return anchors


def links(text, suffix):
    parser = HtmlLinks()
    if suffix == '.html':
        parser.feed(text)
        return parser.links
    text = without_fences(text)
    # Exemplos literais de sintaxe dentro de code spans nao sao links.
    text = re.sub(r'(`+).*?\1', '', text)
    parser.feed(text)
    inline = re.findall(r'!?\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\s*\)', text)
    references = re.findall(r'^\s*\[[^]]+\]:\s*(?:<([^>]+)>|(\S+))', text, re.M)
    return parser.links + [a or b for a, b in inline + references]


def validate(files, root=ROOT):
    errors, checked = [], 0
    for source in files:
        text = source.read_text(encoding='utf-8')
        for target in links(text, source.suffix):
            url = urlsplit(html.unescape(target))
            if url.scheme or url.netloc:
                continue
            checked += 1
            destination = ((root if url.path.startswith('/') else source.parent)
                           / unquote(url.path).lstrip('/')).resolve() if url.path else source
            if not destination.exists():
                errors.append(f'{source.relative_to(root)}: destino ausente: {target}')
                continue
            if url.fragment and destination.suffix in ('.md', '.html'):
                body = destination.read_text(encoding='utf-8')
                parser = HtmlLinks()
                parser.feed(body)
                anchors = parser.anchors
                if destination.suffix == '.md':
                    anchors |= markdown_anchors(body)
                if unquote(url.fragment) not in anchors:
                    errors.append(f'{source.relative_to(root)}: ancora ausente: {target}')
    return checked, errors


def main():
    files = [ROOT / name for name in ('README.md', 'CHANGELOG.md', 'n8n-mirror/README.md')]
    files += sorted((ROOT / 'docs').rglob('*.md'))
    files += sorted((ROOT / 'docs/evidencias').glob('*.html'))
    checked, errors = validate(files)
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'[OK] {checked} links relativos/ancoras em {len(files)} documentos; sem rede')


if __name__ == '__main__':
    main()
