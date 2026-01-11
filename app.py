# --- Load environment variables FIRST ---
from dotenv import load_dotenv
import os

load_dotenv()

# --- Flask core ---
from flask import Flask, render_template, request, redirect, url_for, flash

# --- Email ---
from flask_mail import Mail, Message

# --- Auth ---
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

# --- Security ---
from werkzeug.security import generate_password_hash, check_password_hash

# --- Rate limiting ---
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Database ---
import sqlite3





app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# --- Mail configuration ---
app.config['MAIL_SERVER'] = 'smtpout.secureserver.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database setup
DATABASE = 'celestial_mindworks.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    
    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user:
            return User(user['id'], user['username'], user['password_hash'])
        return None
    
    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if user:
            return User(user['id'], user['username'], user['password_hash'])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

def init_db():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Blog posts table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            body TEXT NOT NULL,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Contact messages table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
if not os.path.exists(DATABASE):
    init_db()

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/modalities')
def modalities():
    return render_template('modalities.html')

@app.route('/approach')
def approach():
    return render_template('approach.html')

# ASTROLOGY COURSES
@app.route('/trainings/astrology/associate')
def course_astrology_associate():
    return render_template('course_astrology_associate.html')

@app.route('/trainings/astrology/practitioner')
def course_astrology_practitioner():
    return render_template('course_astrology_practitioner.html')

@app.route('/trainings/astrology/master')
def course_astrology_master():
    return render_template('course_astrology_master.html')

# HYPNOSIS COURSES
@app.route('/trainings/hypnosis/associate')
def course_hypnosis_associate():
    return render_template('course_hypnosis_associate.html')

@app.route('/trainings/hypnosis/master')
def course_hypnosis_master():
    return render_template('course_hypnosis_master.html')

# MINDFULNESS COURSES
@app.route('/trainings/mindfulness/associate')
def course_mindfulness_associate():
    return render_template('course_mindfulness_associate.html')

@app.route('/trainings/mindfulness/practitioner')
def course_mindfulness_practitioner():
    return render_template('course_mindfulness_practitioner.html')

@app.route('/trainings/mindfulness/master')
def course_mindfulness_master():
    return render_template('course_mindfulness_master.html')

@app.route('/blog')
def blog():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM blog_posts ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('blog.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM blog_posts WHERE slug = ?', (slug,)).fetchone()
    conn.close()
    if post is None:
        return redirect(url_for('blog'))
    return render_template('blog_post.html', post=post)



@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if name and email and message:
            # DB save
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)',
                (name, email, message)
            )
            conn.commit()
            conn.close()

            # EMAIL (this text lives here)
            msg = Message(
                subject="New Contact Form Submission - Celestial Mindworks",
                recipients=[os.environ.get("MAIL_USERNAME")],
                body=f"""
New contact form submission:

Name: {name}
Email: {email}

Message:
{message}
"""
            )
            mail.send(msg)

            flash('Thank you for reaching out. We will respond within 24-48 hours.', 'success')
            return redirect(url_for('contact'))

        else:
            flash('Please fill in all fields.', 'danger')

    return render_template('contact.html')



@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.get_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')


@app.errorhandler(429)
def too_many_requests(e):
    flash("Too many login attempts. Please wait a minute and try again.", "danger")
    return redirect(url_for("login"))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

# Admin routes (protected with login)
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    posts_count = conn.execute('SELECT COUNT(*) as count FROM blog_posts').fetchone()['count']
    messages_count = conn.execute('SELECT COUNT(*) as count FROM contact_messages').fetchone()['count']
    conn.close()
    return render_template('admin_dashboard.html', posts_count=posts_count, messages_count=messages_count)

@app.route('/admin/blog/new', methods=['GET', 'POST'])
@login_required
def admin_new_post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        slug = request.form.get('slug', '').strip()
        body = request.form.get('body', '').strip()
        tags = request.form.get('tags', '').strip()
        
        if title and slug and body:
            conn = get_db_connection()
            try:
                conn.execute(
                    'INSERT INTO blog_posts (title, slug, body, tags) VALUES (?, ?, ?, ?)',
                    (title, slug, body, tags)
                )
                conn.commit()
                conn.close()
                flash('Blog post created successfully!', 'success')
                return redirect(url_for('admin_dashboard'))
            except sqlite3.IntegrityError:
                flash('A post with this slug already exists.', 'danger')
                conn.close()
        else:
            flash('Please fill in all required fields.', 'danger')
    
    return render_template('admin_new_post.html')

@app.route('/admin/messages')
@login_required
def admin_messages():
    conn = get_db_connection()
    messages = conn.execute('SELECT * FROM contact_messages ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin_messages.html', messages=messages)







def create_initial_admin():
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        ("Kiranhsharma",)
    ).fetchone()

    if not user:
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash("Eternal sunshine of the spotless mind")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("Kiranhsharma", password_hash)
        )
        conn.commit()
        print("✅ Admin created")
    else:
        print("ℹ️ Admin already exists")

    conn.close()

create_initial_admin()





if __name__ == '__main__':
    app.run(debug=True)  # Set debug to False for production
