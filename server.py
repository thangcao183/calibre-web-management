import threading
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash

from libs.kobo_device import start_tcp_listener
from libs.watcher import start_watcher
from routes import api_bp, reader_bp

app = Flask(__name__)
app.secret_key = os.urandom(24).hex() # Ideally use a stable key in env for production

app.register_blueprint(api_bp)
app.register_blueprint(reader_bp)

# Basic Config (User can change these in production)
ADMIN_USER = os.getenv("DASHBOARD_USER", "admin")
ADMIN_PASS = os.getenv("DASHBOARD_PASS", "admin")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials!", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

if __name__ == '__main__':
    start_tcp_listener()
    start_watcher()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
