import os
import subprocess
import signal
import shutil
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, g, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_and_secure_key_change_me')
DATABASE = os.path.join(app.root_path, 'database.db')

# --- Database Setup ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# --- Login Manager Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user_data = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['password_hash'])
    return None

# --- Type Conversion Dictionary ---
CONFIG_TYPES = {
    'API_KEY': str,
    'API_SECRET_KEY': str,
    'API_PASSPHRASE': str,
    'TRADING_PAIR': str,
    'LEVERAGE': int,
    'BOT_POLL_INTERVAL': int,
    'MAX_ORDERS_IN_CYCLE': int,
    'DRY_RUN_MODE': bool,
    'LONG_ENABLED': bool,
    'LONG_MARGIN_PER_ORDER_PERCENTAGE': float,
    'LONG_TAKE_PROFIT_PERCENTAGE': float,
    'LONG_ENTRY_PRICE_FALL_PERCENTAGE': float,
    'SHORT_ENABLED': bool,
    'SHORT_MARGIN_PER_ORDER_PERCENTAGE': float,
    'SHORT_TAKE_PROFIT_PERCENTAGE': float,
    'SHORT_ENTRY_PRICE_RISE_PERCENTAGE': float
}

# --- Routes ---
@app.route('/')
@login_required
def index():
    db = get_db()
    config_data = db.execute('SELECT * FROM configs WHERE user_id = ?', (current_user.id,)).fetchone()
    config = dict(config_data) if config_data else {}
    
    bot_info = db.execute('SELECT * FROM bots WHERE user_id = ?', (current_user.id,)).fetchone()
    status = 'Stopped'
    log_file = None

    if bot_info:
        # Always get the log file path if it exists in the DB
        log_file = bot_info['log_file'] 
        
        # Now, check the status of the process
        if bot_info['pid']:
            try:
                os.kill(bot_info['pid'], 0) # Check if process exists
                status = 'Running'
            except (OSError, ProcessLookupError):
                # The process is dead, update DB but PRESERVE the log file path
                db.execute('UPDATE bots SET status = ?, pid = NULL, temp_dir = NULL WHERE user_id = ?', ('Stopped', current_user.id))
                db.commit()
                status = 'Stopped'

    return render_template('index.html', status=status, config=config, log_file=log_file)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user_data = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'], user_data['password_hash'])
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверное имя пользователя или пароль')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        if db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone() is not None:
            flash(f"Пользователь {username} уже существует.")
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        cursor = db.cursor()
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        user_id = cursor.lastrowid
        cursor.execute('INSERT INTO configs (user_id) VALUES (?)', (user_id,))
        cursor.execute('INSERT INTO bots (user_id, status) VALUES (?, ?)', (user_id, 'Stopped'))
        db.commit()
        
        flash('Регистрация прошла успешно! Пожалуйста, войдите.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/start', methods=['POST'])
@login_required
def start_bot():
    stop_bot_process(current_user.id)

    # Process and correctly type the form data
    form_data = {}
    for key, target_type in CONFIG_TYPES.items():
        if target_type == bool:
            form_data[key] = key in request.form
        else:
            value = request.form.get(key)
            try:
                form_data[key] = target_type(value)
            except (ValueError, TypeError):
                # Handle cases where conversion might fail, use a default or flash an error
                form_data[key] = target_type() # e.g., int(), float(), str()

    # Update DB with correctly typed data
    db = get_db()
    db.execute('''
        UPDATE configs SET
            API_KEY=?, API_SECRET_KEY=?, API_PASSPHRASE=?, TRADING_PAIR=?,
            LEVERAGE=?, BOT_POLL_INTERVAL=?, MAX_ORDERS_IN_CYCLE=?, DRY_RUN_MODE=?,
            LONG_ENABLED=?, LONG_MARGIN_PER_ORDER_PERCENTAGE=?, LONG_TAKE_PROFIT_PERCENTAGE=?,
            LONG_ENTRY_PRICE_FALL_PERCENTAGE=?, SHORT_ENABLED=?, SHORT_MARGIN_PER_ORDER_PERCENTAGE=?,
            SHORT_TAKE_PROFIT_PERCENTAGE=?, SHORT_ENTRY_PRICE_RISE_PERCENTAGE=?
        WHERE user_id=?
    ''', (
        form_data['API_KEY'], form_data['API_SECRET_KEY'], form_data['API_PASSPHRASE'], form_data['TRADING_PAIR'],
        form_data['LEVERAGE'], form_data['BOT_POLL_INTERVAL'], form_data['MAX_ORDERS_IN_CYCLE'], form_data['DRY_RUN_MODE'],
        form_data['LONG_ENABLED'], form_data['LONG_MARGIN_PER_ORDER_PERCENTAGE'], form_data['LONG_TAKE_PROFIT_PERCENTAGE'],
        form_data['LONG_ENTRY_PRICE_FALL_PERCENTAGE'], form_data['SHORT_ENABLED'], form_data['SHORT_MARGIN_PER_ORDER_PERCENTAGE'],
        form_data['SHORT_TAKE_PROFIT_PERCENTAGE'], form_data['SHORT_ENTRY_PRICE_RISE_PERCENTAGE'], current_user.id
    ))
    db.commit()

    # Launch bot
    temp_dir = f"/tmp/bot_instance_{current_user.id}_{uuid.uuid4()}"
    bot_source_path = os.path.join(app.root_path, '..', 'okx_hedge_bot1')
    shutil.copytree(bot_source_path, temp_dir)
    
    write_config(os.path.join(temp_dir, 'hedge_config.py'), form_data)

    # Define a unique log file for this bot instance in a persistent directory
    logs_dir = os.path.join(app.root_path, 'user_logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_file_path = os.path.join(logs_dir, f"bot_log_{current_user.id}.log")

    bot_script_path = os.path.join(temp_dir, 'hedge_main.py')
    with open(log_file_path, 'w') as log_file_handle:
        python_executable = os.path.join(app.root_path, 'venv', 'bin', 'python3')
        process = subprocess.Popen(
            [python_executable, '-u', bot_script_path],
            cwd=temp_dir,
            stdout=log_file_handle,
            stderr=subprocess.STDOUT
        )
    
    # Update bot status in DB
    db.execute('UPDATE bots SET status=?, pid=?, temp_dir=?, log_file=? WHERE user_id=?', 
               ('Running', process.pid, temp_dir, log_file_path, current_user.id))
    db.commit()
    
    return redirect(url_for('index'))
@app.route('/stop', methods=['POST'])
@login_required
def stop_bot_route():
    stop_bot_process(current_user.id)
    return redirect(url_for('index'))

@app.route('/get_logs')
@login_required
def get_logs():
    db = get_db()
    bot_info = db.execute('SELECT log_file FROM bots WHERE user_id = ?', (current_user.id,)).fetchone()
    if bot_info and bot_info['log_file'] and os.path.exists(bot_info['log_file']):
        with open(bot_info['log_file'], 'r') as f:
            # Read last 100 lines
            lines = f.readlines()[-100:]
            return jsonify({'logs': "".join(lines)})
    return jsonify({'logs': 'Лог-файл не найден или бот остановлен.'})

# --- Helper Functions ---
def stop_bot_process(user_id):
    db = get_db()
    bot_info = db.execute('SELECT pid, temp_dir FROM bots WHERE user_id = ?', (user_id,)).fetchone()
    if not bot_info:
        return

    pid, temp_dir = bot_info['pid'], bot_info['temp_dir']
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        
    # We keep the log_file path, but clear the pid and temp_dir
    db.execute('UPDATE bots SET status=?, pid=NULL, temp_dir=NULL WHERE user_id=?', ('Stopped', user_id))
    db.commit()

def write_config(file_path, config_data):
    with open(file_path, 'w') as f:
        for key, value in config_data.items():
            if isinstance(value, str):
                f.write(f'{key} = "{value}"\n')
            elif isinstance(value, bool):
                f.write(f"{key} = {value}\n")
            else:
                f.write(f"{key} = {value}\n")

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        print("Database not found. Initializing...")
        init_db()
        print("Database initialized.")
    app.run(debug=True, port=5001)

