from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stevora-secret-key-2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Make sure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def get_db():
    conn = sqlite3.connect('stevora.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profile_pic TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---- ROUTES ----
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('splash.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields required')
            return render_template('signup.html')
        
        hashed = generate_password_hash(password)
        
        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                         (username, email, hashed))
            conn.commit()
            conn.close()
            flash('Account created! Please login')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', username=session.get('username'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    messages = conn.execute('SELECT * FROM messages ORDER BY timestamp ASC LIMIT 100').fetchall()
    conn.close()
    return render_template('chat.html', username=session.get('username'), messages=messages)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---- SOCKET.IO ----
@socketio.on('connect')
def handle_connect():
    print(f"{session.get('username', 'Anonymous')} connected")

@socketio.on('message')
def handle_message(data):
    username = session.get('username', 'Anonymous')
    message = data if isinstance(data, str) else data.get('message', '')
    
    if message:
        conn = get_db()
        conn.execute('INSERT INTO messages (user_id, username, message) VALUES (?, ?, ?)',
                     (session.get('user_id'), username, message))
        conn.commit()
        conn.close()
        
        emit('message', {'username': username, 'message': message}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)