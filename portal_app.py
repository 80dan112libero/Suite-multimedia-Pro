import os
import sqlite3
from pathlib import Path
from functools import wraps

from flask import Flask, jsonify, request, session, send_file, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get('PORTAL_DB', str(BASE_DIR / 'portal_users.db'))

app = Flask(__name__)
app.secret_key = 'suite_multimediale_secret_key_change_me'


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            country TEXT NOT NULL,
            account_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.commit()
    conn.close()


def get_gallery_images():
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
    category_roots = {
        'Emulatori': BASE_DIR / 'emulators',
        'ROM': BASE_DIR / 'Roms',
        'App': BASE_DIR / 'image canali'
    }

    categories = []
    for label, root in category_roots.items():
        items = []
        if root.exists():
            for file_path in sorted(root.rglob('*')):
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    rel_path = file_path.relative_to(BASE_DIR).as_posix()
                    items.append({
                        'name': file_path.name,
                        'image': f'/download/{rel_path}'
                    })
        categories.append({'category': label, 'items': items})

    return {'categories': categories}


init_db()


def require_login(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login richiesto'}), 401
        return view_func(*args, **kwargs)
    return wrapper


@app.route('/')
def index():
    return send_from_directory(str(BASE_DIR / 'site'), 'index.html')


@app.route('/site/<path:filename>')
def static_site(filename):
    return send_from_directory(str(BASE_DIR / 'site'), filename)


@app.route('/styles.css')
def styles_css():
    return send_from_directory(str(BASE_DIR / 'site'), 'styles.css')


@app.route('/app.js')
def app_js():
    return send_from_directory(str(BASE_DIR / 'site'), 'app.js')


@app.route('/api/gallery')
def gallery():
    return jsonify(get_gallery_images())


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    country = (data.get('country') or '').strip()
    account_type = (data.get('account_type') or 'utente').strip()

    if not all([full_name, email, password, country]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO users (full_name, email, password, country, account_type) VALUES (?, ?, ?, ?, ?)',
            (full_name, email, password, country, account_type)
        )
        conn.commit()
        user_id = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()['id']
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email già registrata'}), 409
    finally:
        conn.close()

    session['user_id'] = user_id
    session['email'] = email
    return jsonify({'message': 'Registrazione completata', 'user': {'id': user_id, 'email': email}}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email e password sono obbligatorie'}), 400

    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ? AND password = ?',
        (email, password)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'Credenziali non valide'}), 401

    session['user_id'] = user['id']
    session['email'] = user['email']
    return jsonify({'message': 'Login effettuato', 'session': {'user_id': user['id'], 'email': user['email']}}), 200


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout effettuato'}), 200


@app.route('/api/me')
@require_login
def me():
    conn = get_db_connection()
    user = conn.execute('SELECT id, full_name, email, country, account_type FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return jsonify({'user': dict(user)})


@app.get('/api/apps')
@require_login
def list_apps():
    apps = [
        {'id': 'UniversalEmulatorbyDB.py', 'name': 'Universal Emulator Pro', 'category': 'App', 'path': 'UniversalEmulatorbyDB.py'},
        {'id': 'launch_tv_live_internazionale.py', 'name': 'TV Live', 'category': 'App', 'path': 'launch_tv_live_internazionale.py'},
        {'id': 'mediaplayer.py', 'name': 'Media Player', 'category': 'Media', 'path': 'mediaplayer.py'},
        {'id': 'browser.py', 'name': 'Browser', 'category': 'Web', 'path': 'browser.py'},
        {'id': 'downloader.py', 'name': 'Downloader', 'category': 'Tool', 'path': 'downloader.py'},
        {'id': 'emulators', 'name': 'Emulatori', 'category': 'Emulatori', 'path': 'emulators'}
    ]
    return jsonify({'apps': apps})


@app.route('/download/<path:filename>')
def serve_download(filename):
    safe_path = (BASE_DIR / filename).resolve()
    if not safe_path.exists() or BASE_DIR not in safe_path.parents and safe_path != BASE_DIR:
        return jsonify({'error': 'File non trovato'}), 404

    is_public_image = safe_path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
    if not is_public_image and 'user_id' not in session:
        return jsonify({'error': 'Login richiesto'}), 401

    return send_file(safe_path, as_attachment=not is_public_image)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
