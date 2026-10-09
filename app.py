from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stevora-official-steve-v2-black'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
socketio = SocketIO(app, cors_allowed_origins="*")

DB_NAME = 'stevora.db'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        avatar TEXT DEFAULT 'default.png'
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS message (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # add avatar column if old db exists
    try:
        conn.execute("ALTER TABLE user ADD COLUMN avatar TEXT DEFAULT 'default.png'")
    except:
        pass
    conn.commit()
    conn.close()

init_db()

def get_chat_room(a,b):
    return f"chat_{min(a,b)}_{max(a,b)}"

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('splash.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        conn = get_db()
        try:
            conn.execute("INSERT INTO user (username,email,phone,password) VALUES (?,?,?,?)",
                (request.form['username'], request.form['email'], request.form['phone'],
                 generate_password_hash(request.form['password'])))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except:
            conn.close()
            return "Username/Email taken! <a href='/signup'>Try again</a>"
    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        conn = get_db()
        user = conn.execute("SELECT * FROM user WHERE username=?", (request.form['username'],)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
        return "Wrong password! <a href='/login'>Try again</a>"
    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    me = conn.execute("SELECT * FROM user WHERE id=?", (session['user_id'],)).fetchone()
    users = conn.execute("SELECT * FROM user WHERE id!=?", (session['user_id'],)).fetchall()
    users_data = []
    for u in users:
        last = conn.execute("""SELECT content FROM message WHERE
            (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
            ORDER BY timestamp DESC LIMIT 1""",
            (session['user_id'], u['id'], u['id'], session['user_id'])).fetchone()
        users_data.append({'user': u, 'last': last['content'] if last else 'Tap to start chatting'})
    conn.close()
    return render_template('home.html', users_data=users_data, my_user=me)

@app.route('/profile', methods=['GET','POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute("SELECT * FROM user WHERE id=?", (session['user_id'],)).fetchone()
    if request.method == 'POST':
        file = request.files.get('avatar')
        if file and file.filename:
            filename = secure_filename(f"user_{session['user_id']}_{file.filename}")
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            conn.execute("UPDATE user SET avatar=? WHERE id=?", (filename, session['user_id']))
            conn.commit()
        conn.close()
        return redirect(url_for('home'))
    conn.close()
    return render_template('profile.html', user=user)

@app.route('/chat/<int:user_id>', methods=['GET'])
def chat(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    other = conn.execute("SELECT * FROM user WHERE id=?", (user_id,)).fetchone()
    messages = conn.execute("""SELECT * FROM message WHERE
        (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
        ORDER BY timestamp""", (session['user_id'], user_id, user_id, session['user_id'])).fetchall()
    conn.close()
    if not other:
        return redirect(url_for('home'))
    return render_template('chat.html', other_user=other, messages=messages)

@socketio.on('join')
def on_join(data):
    room = get_chat_room(int(data['sender']), int(data['receiver']))
    join_room(room)

@socketio.on('send_message')
def handle_msg(data):
    sender = int(data['sender'])
    receiver = int(data['receiver'])
    content = data['content']
    if not content.strip():
        return
    conn = get_db()
    conn.execute("INSERT INTO message (sender_id, receiver_id, content) VALUES (?,?,?)", (sender, receiver, content))
    conn.commit()
    conn.close()
    room = get_chat_room(sender, receiver)
    emit('new_message', {
        'sender_id': sender,
        'content': content,
        'time': datetime.now().strftime("%H:%M")
    }, room=room)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, debug=True)