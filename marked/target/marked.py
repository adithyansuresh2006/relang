#!/usr/bin/env python3
import sys
import os
import re
import json
import argparse
from urllib.parse import quote

def escape_html(s, quote=True):
    if not s:
        return ""
    s = str(s)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if quote:
        s = s.replace('"', "&quot;")
        s = s.replace("'", "&#39;")
    return s

def clean_url(url):
    if not url:
        return ""
    try:
        url = quote(url, safe=";/?:@&=+$,-_.!~*'()#%[]")
        url = url.replace("%25", "%")
    except Exception:
        return None
    return url

RE_SPACE = re.compile(r'^(?:[ \t]*(?:\n|$))+')
RE_CODE_INDENT = re.compile(r'^((?: {4}|\t)[^\n]+(?:\n(?:[ \t]*(?:\n|$))*)*)+')
RE_FENCES = re.compile(r'^ {0,3}(`{3,}|~{3,})([^\n]*)(?:\n|$)([\s\S]*?)(?: {0,3}\1[~`]* *(?:\n|$)|$)')
RE_HEADING = re.compile(r'^ {0,3}(#{1,6})(?:\s+([^\n]*?))?(?:[ \t]*#+)? *(?:\n+|$)')
RE_LHEADING = re.compile(r'^([^\n]+)\n {0,3}(=+|-+) *(?:\n+|$)')
RE_HR = re.compile(r'^ {0,3}((?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)')
RE_BLOCKQUOTE = re.compile(r'^( {0,3}>[^\n]*(?:\n[^\n]*)*?)(?:\n\s*\n|$)')
RE_DEF = re.compile(r'^ {0,3}\[([^\]]+)\]: *(?:\n[ \t]*)?([^<\s][^\s]*|<.*?>)(?:(?: +(?:\n[ \t]*)?| *\n[ \t]*)(?:"([^"\\]*)"|\'([^\'\n]*)\'|\(([^()]*)\)))? *(?:\n+|$)', re.IGNORECASE)
RE_TABLE = re.compile(r'^ *([^\n |].*\|.*)\n {0,3}((?:\| *)?:?-+:? *(?:\| *:?-+:? *)*(?:\| *)?)(?:\n((?:(?! *\n|hr|heading|blockquote|code|fences|list|html).*(?:\n|$))*)\n*|$)')

class MarkedParser:
    def parse_markdown(self, src):
        src = src.replace("\r\n", "\n").replace("\r", "\n")
        tokens = self.lex_blocks(src, top=True)
        res = self.render_blocks(tokens)
        if not res.endswith("\n"):
            res += "\n"
        return res + "\n"

    def lex_blocks(self, src, top=True):
        tokens = []
        while src:
            # Space
            m = RE_SPACE.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                if len(raw) == 1 and tokens:
                    tokens[-1]["raw"] += "\n"
                else:
                    tokens.append({"type": "space", "raw": raw})
                continue

            # Fenced Code
            m = RE_FENCES.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                lang = m.group(2).strip()
                code_text = m.group(3) or ""
                tokens.append({"type": "code", "raw": raw, "lang": lang, "text": code_text})
                continue

            # Indented Code
            m = RE_CODE_INDENT.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                lines = raw.split("\n")
                cleaned = []
                for l in lines:
                    if l.startswith("    "): cleaned.append(l[4:])
                    elif l.startswith("\t"): cleaned.append(l[1:])
                    else: cleaned.append(l)
                tokens.append({"type": "code", "raw": raw, "text": "\n".join(cleaned)})
                continue

            # ATX Heading
            m = RE_HEADING.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                depth = len(m.group(1))
                text = (m.group(2) or "").strip()
                tokens.append({"type": "heading", "raw": raw, "depth": depth, "text": text, "tokens": self.lex_inline(text)})
                continue

            # Setext Heading
            m = RE_LHEADING.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                text = m.group(1).strip()
                depth = 1 if m.group(2).startswith("=") else 2
                tokens.append({"type": "heading", "raw": raw, "depth": depth, "text": text, "tokens": self.lex_inline(text)})
                continue

            # HR
            m = RE_HR.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                tokens.append({"type": "hr", "raw": raw})
                continue

            # Blockquote
            m = RE_BLOCKQUOTE.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                lines = raw.split("\n")
                bq_lines = [re.sub(r'^ {0,3}> ?', '', l) for l in lines]
                bq_text = "\n".join(bq_lines)
                tokens.append({"type": "blockquote", "raw": raw, "tokens": self.lex_blocks(bq_text, top=True)})
                continue

            # Table
            m = RE_TABLE.match(src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                headers = [h.strip() for h in m.group(1).strip('|').split('|')]
                aligns = []
                align_specs = [a.strip() for a in m.group(2).strip('|').split('|')]
                for a in align_specs:
                    if a.startswith(':') and a.endswith(':'): aligns.append('center')
                    elif a.endswith(':'): aligns.append('right')
                    elif a.startswith(':'): aligns.append('left')
                    else: aligns.append(None)
                
                rows = []
                if m.group(3):
                    for row_line in m.group(3).strip().split('\n'):
                        if not row_line.strip(): continue
                        cells = [c.strip() for c in row_line.strip('|').split('|')]
                        while len(cells) < len(headers): cells.append("")
                        rows.append(cells[:len(headers)])

                tokens.append({
                    "type": "table",
                    "raw": raw,
                    "header": [{"text": h, "tokens": self.lex_inline(h), "align": aligns[i]} for i, h in enumerate(headers)],
                    "align": aligns,
                    "rows": [[{"text": c, "tokens": self.lex_inline(c), "align": aligns[ci]} for ci, c in enumerate(r)] for r in rows]
                })
                continue

            # Lists
            m_list = re.match(r'^( {0,3}([*+-]|\d{1,9}[.)]))([ \t].*)', src)
            if m_list:
                bullet = m_list.group(2)
                is_ordered = bullet[-1] in ".)"
                start = int(bullet[:-1]) if is_ordered and bullet[:-1].isdigit() else ""
                
                items = []
                item_re = re.compile(r'^( {0,3}(?:[*+-]|\d{1,9}[.)]))[ \t](.*)')
                
                lines = src.split('\n')
                idx = 0
                current_item_lines = []
                indent_level = len(m_list.group(1))
                
                while idx < len(lines):
                    line = lines[idx]
                    m_item = item_re.match(line)
                    if m_item and (len(line) - len(line.lstrip()) < indent_level + 2 or not current_item_lines):
                        new_bullet = m_item.group(1).strip()
                        new_ordered = new_bullet[-1] in ".)"
                        if current_item_lines:
                            if new_ordered != is_ordered:
                                break
                            items.append("\n".join(current_item_lines))
                            current_item_lines = []
                        current_item_lines.append(line)
                    elif current_item_lines:
                        if not line.strip() or line.startswith(" ") or line.startswith("\t"):
                            current_item_lines.append(line)
                        else:
                            break
                    else:
                        break
                    idx += 1

                if current_item_lines:
                    items.append("\n".join(current_item_lines))

                list_raw = "\n".join(lines[:idx])
                if list_raw:
                    src = src[len(list_raw):]
                    if src.startswith("\n"): src = src[1:]
                    
                    parsed_items = []
                    loose = "\n\n" in list_raw or any("\n\n" in item for item in items)
                    for item_str in items:
                        item_first = re.sub(r'^ {0,3}(?:[*+-]|\d{1,9}[.)])[ \t]', '', item_str.split('\n')[0])
                        item_rest = [re.sub(r'^( {1,4}|\t)', '', l) for l in item_str.split('\n')[1:]]
                        item_text = "\n".join([item_first] + item_rest)
                        
                        task = False
                        checked = False
                        m_task = re.match(r'^\[([ xX])\] +(.*)', item_text)
                        if m_task:
                            task = True
                            checked = m_task.group(1).lower() == 'x'
                            item_text = m_task.group(2)

                        item_tokens = self.lex_blocks(item_text, top=False)
                        parsed_items.append({
                            "type": "list_item",
                            "raw": item_str,
                            "text": item_text,
                            "task": task,
                            "checked": checked,
                            "tokens": item_tokens,
                            "loose": loose
                        })

                    tokens.append({
                        "type": "list",
                        "raw": list_raw,
                        "ordered": is_ordered,
                        "start": start,
                        "loose": loose,
                        "items": parsed_items
                    })
                    continue

            # Paragraph
            m = re.match(r'^([^\n]+(?:\n(?!hr|heading|blockquote|code|fences|list|html|table|\s*\n)[^\n]+)*)', src)
            if m:
                raw = m.group(0)
                src = src[len(raw):]
                p_text = raw
                tokens.append({"type": "paragraph", "raw": raw, "tokens": self.lex_inline(p_text)})
                continue

            # Fallback single line
            line = src.split('\n')[0]
            src = src[len(line):]
            if src.startswith('\n'): src = src[1:]
            tokens.append({"type": "paragraph", "raw": line, "tokens": self.lex_inline(line)})

        return tokens

    def lex_inline(self, text):
        tokens = []
        while text:
            # Escape
            m = re.match(r'^\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])', text)
            if m:
                text = text[len(m.group(0)):]
                tokens.append({"type": "escape", "text": m.group(1)})
                continue

            # Codespan
            m = re.match(r'^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)', text)
            if m:
                text = text[len(m.group(0)):]
                c = m.group(2).replace('\n', ' ')
                if c.startswith(' ') and c.endswith(' ') and c.strip(): c = c[1:-1]
                tokens.append({"type": "codespan", "text": c})
                continue

            # Triple (bold + italic)
            m = re.match(r'^(?:\*\*\*([\s\S]+?)\*\*\*|___([\s\S]+?)___)', text)
            if m:
                text = text[len(m.group(0)):]
                inner = m.group(1) or m.group(2)
                tokens.append({"type": "em", "tokens": [{"type": "strong", "text": inner, "tokens": self.lex_inline(inner)}]})
                continue

            # Strong
            m = re.match(r'^(?:\*\*([\s\S]+?)\*\*(?!\*)|(?<!\w)__([\s\S]+?)__(?!\w))', text)
            if m:
                text = text[len(m.group(0)):]
                inner = m.group(1) or m.group(2)
                tokens.append({"type": "strong", "text": inner, "tokens": self.lex_inline(inner)})
                continue

            # Em
            m = re.match(r'^(?:\*([\s\S]+?)\*(?!\*)|(?<!\w)_([\s\S]+?)_(?!\w))', text)
            if m:
                text = text[len(m.group(0)):]
                inner = m.group(1) or m.group(2)
                tokens.append({"type": "em", "text": inner, "tokens": self.lex_inline(inner)})
                continue

            # Del
            m = re.match(r'^~~([^~]+)~~', text)
            if m:
                text = text[len(m.group(0)):]
                inner = m.group(1)
                tokens.append({"type": "del", "text": inner, "tokens": self.lex_inline(inner)})
                continue

            # Link / Image
            m = re.match(r'^!?\[((?:\[[^\]]*\]|[^\[\]])*)\]\(\s*(<[^>]+>|[^\s\)]*)(?:\s+(?:"([^"\\]*)"|\'([^\'\n]*)\'|\(([^()]*)\)))?\s*\)', text)
            if m:
                raw = m.group(0)
                text = text[len(raw):]
                is_img = raw.startswith('!')
                link_text = m.group(1)
                href = m.group(2).strip('<>')
                title = m.group(3) or m.group(4) or m.group(5) or ""
                if is_img:
                    tokens.append({"type": "image", "href": href, "title": title, "text": link_text})
                else:
                    tokens.append({"type": "link", "href": href, "title": title, "text": link_text, "tokens": self.lex_inline(link_text)})
                continue

            # Autolink
            m = re.match(r'^<(https?://[^\s<>]+|[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+)>', text)
            if m:
                text = text[len(m.group(0)):]
                url_str = m.group(1)
                href = ("mailto:" if "@" in url_str and not url_str.startswith("http") else "") + url_str
                tokens.append({"type": "link", "href": href, "text": url_str, "tokens": [{"type": "text", "text": url_str}]})
                continue

            # Br
            m = re.match(r'^(?:  |\\)\n', text)
            if m:
                text = text[len(m.group(0)):]
                tokens.append({"type": "br"})
                continue

            # HTML Tag
            m = re.match(r'^</?[a-zA-Z][\w:-]*(?:\s+[a-zA-Z:_][\w.:-]*(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\'=<>`]+))?)*\s*/?>', text)
            if m:
                raw = m.group(0)
                text = text[len(raw):]
                tokens.append({"type": "html", "text": raw})
                continue

            # Text
            m = re.match(r'^[^\\[`*_~!<]+', text)
            if m:
                text = text[len(m.group(0)):]
                tokens.append({"type": "text", "text": m.group(0)})
                continue

            tokens.append({"type": "text", "text": text[0]})
            text = text[1:]

        return tokens

    def render_item(self, item, loose):
        prefix = ""
        if item.get("task"):
            chk = 'checked="" ' if item.get("checked") else ''
            prefix = f'<input {chk}disabled="" type="checkbox"> '

        toks = item.get("tokens", [])
        if loose:
            return f"<li>{prefix}{self.render_blocks(toks)}</li>\n"
        
        res = prefix
        for tok in toks:
            t = tok.get("type")
            if t == "paragraph" or t == "text":
                res += self.render_inline(tok.get("tokens", []))
            else:
                res += self.render_blocks([tok]).strip()
        return f"<li>{res}</li>\n"

    def render_blocks(self, tokens):
        out = ""
        for token in tokens:
            t = token.get("type")
            if t == "space": continue
            elif t == "heading":
                out += f"<h{token['depth']}>{self.render_inline(token.get('tokens', []))}</h{token['depth']}>\n"
            elif t == "code":
                lang = token.get("lang")
                txt = token.get("text", "")
                if not txt.endswith("\n"): txt += "\n"
                code_esc = escape_html(txt, quote=True)
                if lang: out += f'<pre><code class="language-{escape_html(lang)}">{code_esc}</code></pre>\n'
                else: out += f'<pre><code>{code_esc}</code></pre>\n'
            elif t == "hr":
                out += "<hr>\n"
            elif t == "blockquote":
                out += f"<blockquote>\n{self.render_blocks(token.get('tokens', []))}</blockquote>\n"
            elif t == "list":
                tag = "ol" if token.get("ordered") else "ul"
                start = token.get("start")
                start_attr = f' start="{start}"' if tag == "ol" and start and start != 1 else ""
                items_html = ""
                loose = token.get("loose", False)
                for item in token.get("items", []):
                    items_html += self.render_item(item, loose)
                out += f"<{tag}{start_attr}>\n{items_html}</{tag}>\n"
            elif t == "table":
                header_html = "<tr>\n"
                for cell in token.get("header", []):
                    align = cell.get("align")
                    align_attr = f' align="{align}"' if align else ""
                    cell_text = self.render_inline(cell.get("tokens", []))
                    header_html += f"<th{align_attr}>{cell_text}</th>\n"
                header_html += "</tr>\n"

                rows_html = ""
                for row in token.get("rows", []):
                    rows_html += "<tr>\n"
                    for cell in row:
                        align = cell.get("align")
                        align_attr = f' align="{align}"' if align else ""
                        cell_text = self.render_inline(cell.get("tokens", []))
                        rows_html += f"<td{align_attr}>{cell_text}</td>\n"
                    rows_html += "</tr>\n"
                
                tbody_html = f"<tbody>{rows_html}</tbody>\n" if rows_html else ""
                out += f"<table>\n<thead>\n{header_html}</thead>\n{tbody_html}</table>\n"
            elif t == "html":
                out += token.get("text", "")
            elif t == "paragraph":
                out += f"<p>{self.render_inline(token.get('tokens', []))}</p>\n"
            elif t == "text":
                out += self.render_inline(token.get("tokens", [])) if "tokens" in token else escape_html(token.get("text", ""))
        return out

    def render_inline(self, tokens):
        out = ""
        for token in tokens:
            t = token.get("type")
            if t == "escape" or t == "text":
                out += escape_html(token.get("text", ""))
            elif t == "codespan":
                out += f"<code>{escape_html(token.get('text', ''), quote=True)}</code>"
            elif t == "strong":
                out += f"<strong>{self.render_inline(token.get('tokens', []))}</strong>"
            elif t == "em":
                out += f"<em>{self.render_inline(token.get('tokens', []))}</em>"
            elif t == "del":
                out += f"<del>{self.render_inline(token.get('tokens', []))}</del>"
            elif t == "link":
                href = clean_url(token.get("href", ""))
                if href is None:
                    out += self.render_inline(token.get("tokens", []))
                else:
                    title = token.get("title")
                    title_attr = f' title="{escape_html(title)}"' if title else ""
                    out += f'<a href="{href}"{title_attr}>{self.render_inline(token.get("tokens", []))}</a>'
            elif t == "image":
                href = clean_url(token.get("href", ""))
                alt = escape_html(token.get("text", ""))
                title = token.get("title")
                title_attr = f' title="{escape_html(title)}"' if title else ""
                out += f'<img src="{href}" alt="{alt}"{title_attr}>'
            elif t == "br":
                out += "<br>"
            elif t == "html":
                out += token.get("text", "")
        return out


def main():
    parser = argparse.ArgumentParser(description="Marked Markdown to HTML processor in Python")
    parser.add_argument("-i", "--input", help="Input file")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("-s", "--string", help="Input string")
    parser.add_argument("-t", "--tokens", action="store_true", help="Print token JSON")
    parser.add_argument("files", nargs="*", help="Input markdown files")

    args = parser.parse_args()

    data = ""
    if args.string:
        data = args.string
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = f.read()
    elif args.files:
        with open(args.files[-1], "r", encoding="utf-8") as f:
            data = f.read()
    else:
        data = sys.stdin.read()

    parser_obj = MarkedParser()
    result = parser_obj.parse_markdown(data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        sys.stdout.write(result)

if __name__ == "__main__":
    main()
