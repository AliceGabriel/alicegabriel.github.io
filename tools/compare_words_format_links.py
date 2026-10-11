"""Word-by-word comparison of a saved Jimdo page with the built new page:
text (both directions), bold, italics, headings and link targets.

Build the site first (jekyll build -d /tmp/site), then for each page:

    python3 tools/compare_words_format_links.py tools/jimdo-snapshot/pages/team.html \
        /tmp/site/team/index.html tools/jimdo-snapshot/manifest.json

Optional fourth argument: the address prefix the site was built with. Fifth: how many
differences to list per kind. Expected differences are listed in the project notes
(repaired line-break hyphens, year labels that became headings, merged or unwrapped links).
"""
import sys, re, json, html, unicodedata, difflib, pathlib, urllib.parse
from html.parser import HTMLParser

SKIP = {'script', 'style', 'noscript', 'template', 'svg', 'head', 'nav', 'header', 'footer', 'button'}
VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'wbr', 'area', 'base', 'col', 'embed', 'param', 'track'}
BLOCK = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'section', 'article', 'br', 'tr', 'td', 'th', 'figcaption', 'blockquote', 'ul', 'ol', 'figure', 'main', 'aside'}

class Tokens(HTMLParser):
    """Visible words with their formatting: (word, bold, italic, href, heading level)."""
    def __init__(self, only_main=False):
        super().__init__(convert_charrefs=True)
        self.tokens, self.stack, self.skip = [], [], 0
        self.only_main, self.in_main = only_main, 0
        self.breaks = set()   # token indexes that start a new block
        self.new_block = True
    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if tag == 'br': self.new_block = True
            return
        a = dict(attrs)
        self.stack.append((tag, a))
        if tag in SKIP: self.skip += 1
        if tag == 'main': self.in_main += 1
        if tag in BLOCK: self.new_block = True
    def handle_endtag(self, tag):
        if tag in VOID: return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, _ in self.stack[i:]:
                    if t in SKIP: self.skip -= 1
                    if t == 'main': self.in_main -= 1
                del self.stack[i:]
                break
        if tag in BLOCK: self.new_block = True
    def handle_data(self, data):
        if self.skip or (self.only_main and not self.in_main): return
        tags = [t for t, _ in self.stack]
        bold = any(t in ('strong', 'b') for t in tags)
        ital = any(t in ('em', 'i') for t in tags)
        href = next((a.get('href') for t, a in reversed(self.stack) if t == 'a' and a.get('href')), None)
        head = next((int(t[1]) for t in tags if re.fullmatch(r'h[1-6]', t)), 0)
        text = unicodedata.normalize('NFC', data).replace('­', '')
        for w in re.findall(r'[^\W_]+', text, re.UNICODE):
            if self.new_block:
                self.breaks.add(len(self.tokens)); self.new_block = False
            self.tokens.append((w.lower(), bold, ital, href, head, w))

def norm_href(h, site_host, file_map):
    if not h: return None
    h = html.unescape(h).strip()
    if h in file_map: h = file_map[h]
    p = urllib.parse.urlsplit(h)
    if p.netloc in (site_host, site_host.replace('www.', '')) or (not p.netloc and not p.scheme):
        path = p.path or '/'
        return path if path.startswith('/') else '/' + path
    return h

def main():
    jimdo_file, new_file, manifest_file = sys.argv[1:4]
    base = sys.argv[4] if len(sys.argv) > 4 else ''
    man = json.loads(pathlib.Path(manifest_file).read_text(encoding='utf-8'))
    file_map = {f['from']: f['to'] for f in man.get('files', []) if f.get('to')}
    # also the percent-decoded / escaped variants
    file_map.update({html.unescape(k): v for k, v in list(file_map.items())})
    src = pathlib.Path(jimdo_file).read_text(encoding='utf-8', errors='replace')
    body = src[src.lower().find('<body'):]
    j = Tokens(); j.feed(body)
    n = Tokens(only_main=True); n.feed(pathlib.Path(new_file).read_text(encoding='utf-8'))
    jt, nt = j.tokens, n.tokens
    host = 'www.alicegabriel.com'
    def nh(h, new=False):
        if h and new and base and h.startswith(base + '/'): h = h[len(base):]
        return norm_href(h, host, file_map)
    sm = difflib.SequenceMatcher(None, [t[0] for t in jt], [t[0] for t in nt], autojunk=False)
    out = {'only_jimdo': [], 'only_new': [], 'bold': [], 'italic': [], 'href': [], 'heading': []}
    def ctx(tokens, i0, i1, pad=5):
        return ' '.join(t[5] for t in tokens[max(0, i0 - pad):i0]) + ' >>> ' + ' '.join(t[5] for t in tokens[i0:i1]) + ' <<< ' + ' '.join(t[5] for t in tokens[i1:i1 + pad])
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == 'equal':
            run = {'bold': None, 'italic': None, 'href': None, 'heading': None}
            def flush(kind):
                if run[kind]:
                    s, e, detail = run[kind]
                    out[kind].append((ctx(jt, s, e), detail)); run[kind] = None
            for k in range(a1 - a0):
                a, b = jt[a0 + k], nt[b0 + k]
                checks = {'bold': (a[1], b[1]), 'italic': (a[2], b[2]), 'href': (nh(a[3]), nh(b[3], True)), 'heading': (bool(a[4]), bool(b[4]))}
                for kind, (x, y) in checks.items():
                    if x != y:
                        detail = f'jimdo={x!r} new={y!r}'
                        if run[kind] and run[kind][1] == a0 + k and run[kind][2] == detail:
                            run[kind] = (run[kind][0], a0 + k + 1, detail)
                        else:
                            flush(kind); run[kind] = (a0 + k, a0 + k + 1, detail)
                    else:
                        flush(kind)
            for kind in run: flush(kind)
        else:
            if a1 > a0: out['only_jimdo'].append(ctx(jt, a0, a1))
            if b1 > b0: out['only_new'].append(ctx(nt, b0, b1))
    print(f'words: jimdo {len(jt)}, new {len(nt)}, matching ratio {sm.ratio():.4f}')
    for kind, label in [('only_jimdo', 'TEXT ONLY ON JIMDO'), ('only_new', 'TEXT ONLY ON THE NEW PAGE'), ('href', 'LINK TARGET DIFFERS'), ('bold', 'BOLD DIFFERS'), ('italic', 'ITALIC DIFFERS'), ('heading', 'HEADING/TEXT ROLE DIFFERS')]:
        items = out[kind]
        print(f'-- {label}: {len(items)}')
        for it in items[:int(sys.argv[5]) if len(sys.argv) > 5 else 60]:
            if isinstance(it, tuple): print('     ', it[0][:230], '\n          ', it[1][:260])
            else: print('     ', it[:300])
main()
