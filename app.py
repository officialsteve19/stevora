from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stevora-secret-123'

# threading mode works with Render gthread worker
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ---- PAGES ----
@app.route('/')
def splash():
    return render_template('splash.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # you can add DB logic here later
        return redirect(url_for('home'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

# ---- SOCKET CHAT ----
@socketio.on('message')
def handle_message(msg):
    print(f"Message: {msg}")
    emit('message', msg, broadcast=True)

@socketio.on('connect')
def handle_connect():
    print("User connected")

if __name__ == '__main__':
    socketio.run(app, debug=True)