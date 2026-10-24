# 只用標準函式庫，把測試計畫.md 轉成可列印的 HTML（只支援這份文件用到的語法）
import html
import re
import sys

CSS = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
:root { --ink: #1d1f21; --muted: #5b6168; --line: #c9ced4; --head: #eef1f4; --accent: #1f5f8b; }
html { background: #fff; }
body { font-family: "PingFang TC", "Heiti TC", "Noto Sans TC", sans-serif; color: var(--ink);
  font-size: 10pt; line-height: 1.65; margin: 0; }
h1 { font-size: 19pt; margin: 0 0 6pt; color: var(--accent); }
h2 { font-size: 14pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5pt solid var(--accent);
  color: var(--accent); break-after: avoid; }
h2.newpage { break-before: page; margin-top: 0; }
h3 { font-size: 11.5pt; margin: 13pt 0 4pt; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 10pt 0 3pt; break-after: avoid; }
p { margin: 4pt 0 6pt; }
ul, ol { margin: 3pt 0 6pt; padding-left: 18pt; }
li { margin: 2pt 0; }
li > p { margin: 3pt 0; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 8.6pt; background: #f2f4f6;
  padding: 0 2pt; border-radius: 2pt; }
pre { background: #f5f7f9; border: 0.5pt solid var(--line); padding: 6pt 8pt; white-space: pre-wrap;
  word-break: break-all; font-size: 8.4pt; line-height: 1.45; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 9pt; font-size: 8.6pt; line-height: 1.5; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 0.5pt solid var(--line); padding: 3pt 5pt; vertical-align: top; text-align: left;
  overflow-wrap: break-word; }
th { background: var(--head); font-weight: 600; }
td:first-child { font-weight: 500; }
strong { font-weight: 700; }
nav.toc { border: 0.5pt solid var(--line); background: #fafbfc; padding: 6pt 10pt; margin: 8pt 0 4pt;
  font-size: 9.4pt; columns: 2; column-gap: 18pt; }
nav.toc div { margin: 1pt 0; break-inside: avoid; }
nav.toc .sub { padding-left: 12pt; color: var(--muted); }
.meta { color: var(--muted); font-size: 9pt; }
"""


def inline(t):
    # 先把 code span 抽出，避免內容被當成粗體或連結
    codes = []

    def keep(m):
        codes.append('<code>' + html.escape(m.group(1)) + '</code>')
        return '\x00%d\x00' % (len(codes) - 1)

    t = re.sub(r'`([^`]+)`', keep, t)
    t = html.escape(t, quote=False).replace('&lt;br&gt;', '<br>')
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', t)  # PDF 裡本機連結無效，只留文字
    return re.sub(r'\x00(\d+)\x00', lambda m: codes[int(m.group(1))], t)


def cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def indent(l):
    return len(l) - len(l.lstrip(' '))


LIST_RE = re.compile(r'^( *)([-*]|\d+\.) (.*)$')


def parse_list(lines, i, base):
    """從第 i 行解析一個縮排為 base 的清單，回傳 (html, 下一行)"""
    m = LIST_RE.match(lines[i])
    ordered = m.group(2)[0].isdigit()
    tag = 'ol' if ordered else 'ul'
    start = int(m.group(2)[:-1]) if ordered else 1
    out = ['<%s%s>' % (tag, ' start="%d"' % start if ordered and start != 1 else '')]
    while i < len(lines):
        m = LIST_RE.match(lines[i])
        if not m or len(m.group(1)) != base or (m.group(2)[0].isdigit()) != ordered:
            break
        body_indent = base + len(m.group(2)) + 1
        item = [inline(m.group(3))]
        i += 1
        para = []
        while i < len(lines):
            l = lines[i]
            if not l.strip():
                # 空行後若還有更深縮排的內容，仍屬於同一項
                j = i + 1
                if j < len(lines) and lines[j].strip() and indent(lines[j]) >= body_indent:
                    if para:
                        item.append('<p>' + inline(' '.join(para)) + '</p>')
                        para = []
                    i = j
                    continue
                break
            if indent(l) < body_indent:
                break
            sm = LIST_RE.match(l)
            if sm and len(sm.group(1)) >= body_indent:
                if para:
                    item.append('<p>' + inline(' '.join(para)) + '</p>')
                    para = []
                sub, i = parse_list(lines, i, len(sm.group(1)))
                item.append(sub)
                continue
            if l.strip().startswith('```'):
                code = []
                i += 1
                while not lines[i].strip().startswith('```'):
                    code.append(lines[i][body_indent:])
                    i += 1
                i += 1
                item.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
                continue
            para.append(l.strip())
            i += 1
        if para:
            item.append('<p>' + inline(' '.join(para)) + '</p>')
        out.append('<li>' + ''.join(item) + '</li>')
    out.append('</%s>' % tag)
    return '\n'.join(out), i


def convert(md):
    lines = md.splitlines()
    out, toc = [], []
    i, n_h2 = 0, 0
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            i += 1
            continue
        if l.startswith('```'):
            code = []
            i += 1
            while not lines[i].startswith('```'):
                code.append(lines[i])
                i += 1
            i += 1
            out.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
            continue
        m = re.match(r'^(#{1,4}) (.*)$', l)
        if m:
            lv, text = len(m.group(1)), m.group(2)
            hid = 'h%d' % len(toc)
            cls = ''
            if lv == 2:
                n_h2 += 1
                # 附錄 A 從新的一頁開始
                if text.startswith('附錄 A'):
                    cls = ' class="newpage"'
            if lv in (2, 3):
                toc.append((lv, hid, text))
            out.append('<h%d id="%s"%s>%s</h%d>' % (lv, hid, cls, inline(text), lv))
            if lv == 1:
                out.append('<!--TOC-->')
            i += 1
            continue
        if l.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append(cells(lines[i]))
                i += 1
            head, body = rows[0], rows[2:]
            t = ['<table><thead><tr>' + ''.join('<th>%s</th>' % inline(c) for c in head) + '</tr></thead><tbody>']
            for r in body:
                assert len(r) == len(head), r
                t.append('<tr>' + ''.join('<td>%s</td>' % inline(c) for c in r) + '</tr>')
            t.append('</tbody></table>')
            out.append('\n'.join(t))
            continue
        if LIST_RE.match(l):
            h, i = parse_list(lines, i, indent(l))
            out.append(h)
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('|', '#', '```')) \
                and not LIST_RE.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append('<p>' + inline(' '.join(para)) + '</p>')
    # 目錄只列第 1 節和附錄的大標，第 2～3 節列到小節
    items = []
    for lv, hid, text in toc:
        if lv == 3 and not re.match(r'\d\.\d', text):
            continue
        cls = ' class="sub"' if lv == 3 else ''
        items.append('<div%s>%s</div>' % (cls, inline(text)))
    nav = '<nav class="toc">' + ''.join(items) + '</nav>'
    return '\n'.join(out).replace('<!--TOC-->', '<!--TOC-->', 1), nav


def main():
    src, dst = sys.argv[1], sys.argv[2]
    md = open(src, encoding='utf-8').read()
    body, nav = convert(md)
    # 目錄放在開頭說明之後、第 1 節之前
    body = body.replace('<!--TOC-->', '', 1)
    k = body.index('<h2')
    body = body[:k] + nav + '\n' + body[k:]
    title = re.match(r'# (.*)', md).group(1)
    doc = ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>%s</title><style>%s</style></head><body>%s</body></html>'
           % (html.escape(title), CSS, body))
    open(dst, 'w', encoding='utf-8').write(doc)


main()
