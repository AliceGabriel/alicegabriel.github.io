"""Comparison of the visible text of a saved Jimdo page and the built new page,
word by word and punctuation mark by punctuation mark (asterisks, quotation marks, dashes).

Build the site first (jekyll build -d /tmp/site), then for each page:

    python3 tools/compare_every_character.py tools/jimdo-snapshot/pages/publications.html \
        /tmp/site/publications/index.html
"""
import sys, re, html, unicodedata, difflib, pathlib, collections
from html.parser import HTMLParser
SKIP = {'script', 'style', 'noscript', 'template', 'svg', 'head', 'nav', 'header', 'footer', 'button'}
VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'wbr'}
class Text(HTMLParser):
    def __init__(self, only_main=False):
        super().__init__(convert_charrefs=True)
        self.parts, self.stack, self.skip, self.only_main, self.in_main = [], [], 0, only_main, 0
    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            self.parts.append(' '); return
        self.stack.append(tag)
        if tag in SKIP: self.skip += 1
        if tag == 'main': self.in_main += 1
        self.parts.append(' ' if tag in ('p', 'li', 'div', 'h1', 'h2', 'h3', 'h4', 'td', 'figcaption', 'ul', 'ol') else '')
    def handle_endtag(self, tag):
        if tag in VOID: return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i] == tag:
                for t in self.stack[i:]:
                    if t in SKIP: self.skip -= 1
                    if t == 'main': self.in_main -= 1
                del self.stack[i:]; break
        self.parts.append(' ' if tag in ('p', 'li', 'div', 'h1', 'h2', 'h3', 'h4', 'td', 'figcaption', 'ul', 'ol') else '')
    def handle_data(self, data):
        if self.skip or (self.only_main and not self.in_main): return
        self.parts.append(data)
def tokens(text):
    text = unicodedata.normalize('NFC', text).replace('­', '').replace(' ', ' ').replace('​', '')
    return re.findall(r'[^\W_]+|[^\w\s]|_', text, re.UNICODE)
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
j = Text(); j.feed(src[src.lower().find('<body'):])
n = Text(only_main=True); n.feed(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
jt, nt = tokens(''.join(j.parts)), tokens(''.join(n.parts))
sm = difflib.SequenceMatcher(None, jt, nt, autojunk=False)
kinds = collections.Counter(); examples = collections.defaultdict(list)
for op, a0, a1, b0, b1 in sm.get_opcodes():
    if op == 'equal': continue
    a, b = ' '.join(jt[a0:a1]), ' '.join(nt[b0:b1])
    key = (a, b)
    kinds[key] += 1
    if len(examples[key]) < 2:
        examples[key].append(' '.join(jt[max(0, a0 - 7):a0]) + ' [[' + a + ' => ' + b + ']] ' + ' '.join(jt[a1:a1 + 6]))
print(f'tokens: jimdo {len(jt)}, new {len(nt)}; differing spots {sum(kinds.values())}, kinds {len(kinds)}')
for (a, b), c in kinds.most_common(int(sys.argv[3]) if len(sys.argv) > 3 else 80):
    print(f'{c:4d} x  {a!r} => {b!r}')
    for ex in examples[(a, b)]:
        print('          ', ex[:210])
