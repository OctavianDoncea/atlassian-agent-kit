from __future__ import annotations
from bs4 import BeautifulSoup
from markdownify import markdownify as md

_PANEL_LABELS = {'info': 'Note', 'note': 'Note', 'warning': 'Warning', 'tip': 'Tip'}

def _convert_code_macros(soup: BeautifulSoup) -> None:
    for macro in soup.find_all('ac:structured-macro'):
        name = macro.get('ac:name')
        if name == 'code':
            body = macro.find('ac:plain-text-body')
            lang_tag = macro.find('ac:parameter', attrs={'ac:name': 'language'})
            pre = soup.new_tag('pre')
            code = soup.new_tag('code')

            if lang_tag:
                code['class'] = lang_tag.get_text(strip=True)

            code.string = body.get_text() if body else ''
            pre.append(code)
            macro.replace_with(pre)
        elif name in _PANEL_LABELS:
            label = _PANEL_LABELS[name]
            rich = macro.find('ac:rich-text-body')
            bq = soup.new_tag('blockquote')
            p = soup.new_tag('p')
            strong = soup.new_tag('strong')
            strong.string = f'{label}:'
            p.append(strong)
            p.append(' ')

            if rich:
                for child in list(rich.children):
                    p.append(child.extract())
            
            bq.append(p)
            macro.replace_with(bq)
        else:
            # Unknown macro
            marker = soup.new_tag('p')
            marker.string = f'[{name} macro]'
            macro.replace_with(marker)

def _convert_links(soup: BeautifulSoup) -> None:
    for link in soup.find_all('ac:link'):
        page = link.find('ri:page')
        url_tag = link.find('ri:url')
        body = link.find('ac:plain-text-body-link') or link.find('ac:link-body')

        if url_tag is not None:
            href = url_tag.get('ri:value', '')
            label = body.get_text(strip=True) if body else href
        elif page is not None:
            href = f"#{page.get('ri:content-title', '')}"
            label = body.get_text(strip=True) if body else page.get('ri:content-title', 'page')
        else:
            link.extract()
            continue
    
        a = soup.new_tag('a', href=href)
        a.string = label
        link.replace_with(a)

def _convert_images(soup: BeautifulSoup) -> None:
    for image in soup.find_all('ac:image'):
        att = image.find('ri:attachment')
        url_tag = image.find('ri:url')
        src = att.get('ri:filename') if att is not None else (url_tag.get('ri:value') if url_tag is not None else 'image')
        img = soup.new_tag('img', src=src, alt='image')
        image.replace_with(img)

def _strip_leftovers(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(['ac:parameter', 'ac:plain-text-body', 'ri:page', 'ri:url', 'ri:attachment']):
        tag.extract()

def storage_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html or '', 'html.parser')
    _convert_code_macros(soup)
    _convert_links(soup)
    _convert_images(soup)
    _strip_leftovers(soup)

    text = md(str(soup), heading_style='ATX', bullets='-')

    out: list[str] = []
    for line in (ln.rstrip() for ln in text.splitlines()):
        if line.strip() == '' and out and out[-1].strip() == '':
            continue
        out.append(line)

    return '\n'.join(out).strip() + '\n'