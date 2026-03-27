import re
import zipfile
import os
from bs4 import BeautifulSoup, NavigableString, Tag

def split_sentences(text):
    # Matches chunks of text up to the sentence boundary (., !, ?) plus optional quotes and trailing whitespace
    # Fallback to matching any chunk of characters not containing ., !, ?
    pattern = re.compile(r'[^.!?]*[.!?]+[\'"”’“…]*\s*|[^.!?]+')
    chunks = [m.group(0) for m in pattern.finditer(text) if m.group(0)]
    return chunks

def kepubify_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Provide Kobo Div wrappers
    body = soup.body
    if not body:
        return html_content
        
    # Check if already kepubified
    if body.find(class_="koboSpan"):
        return html_content
        
    book_columns = body.find(id="book-columns")
    if not book_columns:
        book_columns = soup.new_tag("div", id="book-columns")
        book_inner = soup.new_tag("div", id="book-inner")
        
        # Move all children of body to book-inner
        for child in list(body.children):
            book_inner.append(child)
            
        book_columns.append(book_inner)
        body.append(book_columns)
        
    # 2. Add Kobo spans
    # Create persistent variable state using lists for closures
    para = [0]
    seg = [0]
    inc_para_next = [False]
    
    block_tags = {'p', 'ol', 'ul', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div'}
    ignore_tags = {'script', 'style', 'pre', 'audio', 'video', 'svg', 'math'}
    
    def process_node(node):
        if isinstance(node, Tag):
            if node.name == 'img':
                para[0] += 1
                seg[0] = 1
                inc_para_next[0] = False
                
                # Wrap img in koboSpan
                span = soup.new_tag("span", **{"class": "koboSpan", "id": f"kobo.{para[0]}.{seg[0]}"})
                node.insert_before(span)
                span.append(node)
                
            elif node.name in ignore_tags:
                return
            else:
                if node.name in block_tags:
                    inc_para_next[0] = True
                
                # Safely iterate over a copy of children since we modify the DOM
                for child in list(node.children):
                    process_node(child)
                    
        elif isinstance(node, NavigableString):
            text = str(node)
            if not text.strip() and node.parent.name != 'p':
                # Preserve whitespace pure blocks outside paragraphs
                return
            
            sentences = split_sentences(text)
            if not sentences:
                return
                
            parent = node.parent
            idx = parent.index(node)
            node.extract()  # Remove original string
            
            current_insert_pos = idx
            for sentence in sentences:
                if not sentence.strip() and parent.name != 'p':
                    # Pure space chunk, insert as standard NavigableString
                    parent.insert(current_insert_pos, NavigableString(sentence))
                    current_insert_pos += 1
                else:
                    if inc_para_next[0]:
                        para[0] += 1
                        seg[0] = 0
                        inc_para_next[0] = False
                    seg[0] += 1
                    
                    span = soup.new_tag("span", **{"class": "koboSpan", "id": f"kobo.{para[0]}.{seg[0]}"})
                    span.string = sentence
                    parent.insert(current_insert_pos, span)
                    current_insert_pos += 1

    # Start DFS processing from the body element
    process_node(body)
    
    return str(soup)

def transform_opf(opf_content):
    soup = BeautifulSoup(opf_content, 'xml')
    cover_meta = soup.find('meta', attrs={'name': 'cover'})
    cover_id = cover_meta['content'] if cover_meta else 'cover'
    
    cover_item = soup.find('item', id=cover_id)
    if cover_item:
        props = cover_item.get('properties', '').split()
        if 'cover-image' not in props:
            props.append('cover-image')
            cover_item['properties'] = ' '.join(props)
            
    return str(soup)

def convert_to_kepub(input_epub_path, output_epub_path):
    """
    Reads an EPUB ZIP archive, processes all HTML/XHTML files to inject Kobo Spans,
    and writes back to a new ZIP archive (the KePub).
    """
    with zipfile.ZipFile(input_epub_path, 'r') as zin:
        with zipfile.ZipFile(output_epub_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                content = zin.read(item.filename)
                
                if item.filename.endswith(('.html', '.xhtml', '.htm')):
                    try:
                        html_str = content.decode('utf-8')
                        kepub_html = kepubify_html(html_str)
                        content = kepub_html.encode('utf-8')
                    except Exception as e:
                        print(f"[KePub Converter] Error processing HTML {item.filename}: {e}")
                elif item.filename.endswith('.opf'):
                    try:
                        opf_str = content.decode('utf-8')
                        new_opf = transform_opf(opf_str)
                        content = new_opf.encode('utf-8')
                    except Exception as e:
                        print(f"[KePub Converter] Error processing OPF {item.filename}: {e}")
                        
                zout.writestr(item, content)
                
    return output_epub_path
