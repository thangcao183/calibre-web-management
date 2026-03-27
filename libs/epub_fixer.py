import zipfile
import tempfile
import os
import shutil

def fix_epub(epub_path):
    """
    Fix common EPUB issues like missing UTF-8 declarations
    to prevent Kobo/Amazon failing to parse the file properly.
    """
    print(f"[EPUB Fixer] Checking {os.path.basename(epub_path)}")
    temp_fd, temp_path = tempfile.mkstemp(suffix='.epub')
    os.close(temp_fd)
    
    modified = False
    
    try:
        with zipfile.ZipFile(epub_path, 'r') as zin:
            infolist = zin.infolist()
            
            with zipfile.ZipFile(temp_path, 'w') as zout:
                # EPUB spec: mimetype must be first and uncompressed
                mimetype_item = next((i for i in infolist if i.filename == 'mimetype'), None)
                if mimetype_item:
                    content = zin.read(mimetype_item.filename)
                    # Create a new info object to ensure it's not compressed
                    zinfo = zipfile.ZipInfo('mimetype')
                    zinfo.compress_type = zipfile.ZIP_STORED
                    zout.writestr(zinfo, content)
                
                for item in infolist:
                    if item.filename == 'mimetype':
                        continue
                        
                    content = zin.read(item.filename)
                    
                    if item.filename.endswith(('.html', '.xhtml', '.opf', '.ncx')):
                        try:
                            # Try to process text files for common issues
                            text = content.decode('utf-8')
                            made_change = False
                            
                            # 1. Fix missing UTF-8 in XML declaration
                            if text.startswith('<?xml version="1.0"?>'):
                                text = text.replace('<?xml version="1.0"?>', '<?xml version="1.0" encoding="utf-8"?>', 1)
                                made_change = True
                                
                            # 2. Add charset meta tag in HTML head if missing
                            if item.filename.endswith(('.html', '.xhtml')):
                                if '<head>' in text and 'charset=' not in text.lower():
                                    text = text.replace('<head>', '<head>\n  <meta charset="utf-8" />', 1)
                                    made_change = True
                                    
                            if made_change:
                                content = text.encode('utf-8')
                                modified = True
                        except UnicodeDecodeError:
                            pass
                            
                    # Everything else is compressed
                    zout.writestr(item, content, compress_type=zipfile.ZIP_DEFLATED)
                    
        if modified:
            os.chmod(temp_path, 0o644)
            shutil.move(temp_path, epub_path)
            print(f"[EPUB Fixer] Applied fixes to {os.path.basename(epub_path)}.")
            return True
        else:
            os.remove(temp_path)
            return False
            
    except Exception as e:
        print(f"[EPUB Fixer] Failed to process {epub_path}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
