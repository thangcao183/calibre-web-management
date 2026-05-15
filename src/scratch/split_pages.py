import re
import os

base_dir = '/home/wolf/CODE/Python/Ebook/KOBO/calibre-web-management/src'
index_path = os.path.join(base_dir, 'templates/index.html')
ttv_path = os.path.join(base_dir, 'templates/ttv.html')
server_path = os.path.join(base_dir, 'server.py')

with open(index_path, 'r', encoding='utf-8') as f:
    index_html = f.read()

ttv_html = index_html

# Fix navbar links in ttv.html
ttv_html = re.sub(r'<a class="cwa-nav-item(.*?)" href="#(section-[^"]+)" data-section="[^"]+">',
                  r'<a class="cwa-nav-item\1" href="/#\2">', ttv_html)
# Make TTV active in ttv.html
ttv_html = re.sub(r'<a class="cwa-nav-item active" href="/#section-library">',
                  r'<a class="cwa-nav-item" href="/#section-library">', ttv_html)
ttv_html = re.sub(r'<a class="cwa-nav-item" href="#section-ttv" data-section="section-ttv">',
                  r'<a class="cwa-nav-item active" href="/ttv">', ttv_html)

# Remove other sections from main in ttv.html
ttv_html = re.sub(r'<!-- Calibre Library -->.*?(?=<div class="card glass-card mt-3" id="section-settings">)', '', ttv_html, flags=re.DOTALL)
ttv_html = re.sub(r'<div class="card glass-card mt-3" id="section-settings">.*?(?=<div class="card glass-card mt-3" id="section-ttv">)', '', ttv_html, flags=re.DOTALL)

# Remove bookModal and Selection Bar from ttv.html
ttv_html = re.sub(r'<!-- Book Action Modal \(Bootstrap\) -->.*?(?=<!-- Selection Bar -->)', '', ttv_html, flags=re.DOTALL)
ttv_html = re.sub(r'<!-- Selection Bar -->.*?(?=<script src=")', '', ttv_html, flags=re.DOTALL)

# In ttv.html, we don't need library.js etc, but leaving them is fine for now or we can remove them.
ttv_html = re.sub(r'<script src="/static/js/library.js"></script>\n', '', ttv_html)
ttv_html = re.sub(r'<script src="/static/js/modal-actions.js"></script>\n', '', ttv_html)

# Write ttv.html
with open(ttv_path, 'w', encoding='utf-8') as f:
    f.write(ttv_html)

# Fix index.html
new_index_html = re.sub(r'<a class="cwa-nav-item" href="#section-ttv" data-section="section-ttv">',
                        r'<a class="cwa-nav-item" href="/ttv">', index_html)

new_index_html = re.sub(r'<div class="card glass-card mt-3" id="section-ttv">.*?(?=</main>)', '', new_index_html, flags=re.DOTALL)
new_index_html = re.sub(r'<!-- TTV Story Detail Modal -->.*?(?=<!-- Book Action Modal)', '', new_index_html, flags=re.DOTALL)
new_index_html = re.sub(r'<script src="/static/js/ttv.js"></script>\n', '', new_index_html)

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(new_index_html)

# Update server.py
with open(server_path, 'r', encoding='utf-8') as f:
    server_code = f.read()

if "@app.route('/ttv')" not in server_code:
    route_code = """
@app.route('/ttv')
def ttv():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('ttv.html')
"""
    server_code = server_code.replace("if __name__ == '__main__':", route_code + "\nif __name__ == '__main__':")
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(server_code)

print("Split completed successfully.")
