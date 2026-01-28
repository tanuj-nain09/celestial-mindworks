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

# --- PostgreSQL ---
import psycopg2
from psycopg2.extras import RealDictCursor

# --------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# --- Mail configuration ---
app.config["MAIL_SERVER"] = "smtpout.secureserver.net"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

mail = Mail(app)

# --- Rate limiter ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# --- Login manager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db_connection():
    return psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor,
        sslmode="require"
    )
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            body TEXT NOT NULL,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


# Initialize DB safely on startup
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print("DB init failed:", e)


# --------------------------------------------------
# AUTH
# --------------------------------------------------

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return User(user["id"], user["username"], user["password_hash"])
        return None

    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return User(user["id"], user["username"], user["password_hash"])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/modalities")
def modalities():
    return render_template("modalities.html")

@app.route("/approach")
def approach():
    return render_template("approach.html")

@app.route("/blog")
def blog():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blog_posts ORDER BY created_at DESC")
    posts = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("blog.html", posts=posts)

@app.route("/blog/<slug>")
def blog_post(slug):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blog_posts WHERE slug = %s", (slug,))
    post = cur.fetchone()
    cur.close()
    conn.close()
    if not post:
        return redirect(url_for("blog"))
    return render_template("blog_post.html", post=post)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if name and email and message:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO contact_messages (name, email, message) VALUES (%s, %s, %s)",
                (name, email, message)
            )
            conn.commit()
            cur.close()
            conn.close()

            msg = Message(
                subject="New Contact Form Submission - Celestial Mindworks",
                recipients=[os.environ.get("MAIL_USERNAME")],
                body=f"""
Name: {name}
Email: {email}

Message:
{message}
"""
            )
            mail.send(msg)

            flash("Thank you for reaching out. We will respond within 24-48 hours.", "success")
            return redirect(url_for("contact"))

        flash("Please fill in all fields.", "danger")

    return render_template("contact.html")

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.get_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM blog_posts")
    posts_count = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM contact_messages")
    messages_count = cur.fetchone()["count"]

    # ADD THIS
    cur.execute("""
        SELECT id, title, slug, created_at
        FROM blog_posts
        ORDER BY created_at DESC
        LIMIT 5
    """)
    posts = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        posts_count=posts_count,
        messages_count=messages_count,
        posts=posts
    )

@app.route("/admin/blog/new", methods=["GET", "POST"])
@login_required
def admin_new_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip()
        body = request.form.get("body", "").strip()
        tags = request.form.get("tags", "").strip()

        if title and slug and body:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO blog_posts (title, slug, body, tags) VALUES (%s, %s, %s, %s)",
                    (title, slug, body, tags)
                )
                conn.commit()
                flash("Blog post created successfully!", "success")
                return redirect(url_for("admin_dashboard"))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                flash("Slug already exists.", "danger")
            finally:
                cur.close()
                conn.close()

        else:
            flash("Please fill in all required fields.", "danger")

    return render_template("admin_new_post.html")

@app.route("/admin/messages")
@login_required
def admin_messages():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM contact_messages ORDER BY created_at DESC")
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin_messages.html", messages=messages)


@app.route("/admin/blog/delete/<int:post_id>", methods=["POST"])
@login_required
def admin_delete_post(post_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM blog_posts WHERE id = %s", (post_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Blog post deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/faq")
def faq():
    return render_template("faq.html")

# --------------------------------------------------
# TRAININGS
# --------------------------------------------------

# ASTROLOGY
@app.route("/trainings/astrology/associate")
def course_astrology_associate():
    return render_template("course_astrology_associate.html")

@app.route("/trainings/astrology/practitioner")
def course_astrology_practitioner():
    return render_template("course_astrology_practitioner.html")

@app.route("/trainings/astrology/master")
def course_astrology_master():
    return render_template("course_astrology_master.html")


# HYPNOSIS
@app.route("/trainings/hypnosis/associate")
def course_hypnosis_associate():
    return render_template("course_hypnosis_associate.html")

@app.route("/trainings/hypnosis/practitioner")
def course_hypnosis_practitioner():
    return render_template("course_hypnosis_associate.html")

@app.route("/trainings/hypnosis/master")
def course_hypnosis_master():
    return render_template("course_hypnosis_master.html")


# MINDFULNESS
@app.route("/trainings/mindfulness/associate")
def course_mindfulness_associate():
    return render_template("course_mindfulness_associate.html")

@app.route("/trainings/mindfulness/practitioner")
def course_mindfulness_practitioner():
    return render_template("course_mindfulness_practitioner.html")

@app.route("/trainings/mindfulness/master")
def course_mindfulness_master():
    return render_template("course_mindfulness_master.html")

# SYMBOLIC INTELLIGENCE

@app.route("/trainings/symbolic-intelligence/associate")
def course_symbolic_intelligence_associate():
    return render_template("symbolic_intelligence.html")

@app.route("/trainings/symbolic-intelligence/practitioner")
def course_symbolic_intelligence_practitioner():
    return render_template("symbolic_intelligence.html")

@app.route("/trainings/symbolic-intelligence/master")
def course_symbolic_intelligence_master():
    return render_template("symbolic_intelligence.html")

# INTEGRAL SYMBOLIC YOGA

@app.route("/trainings/integral-symbolic-yoga/associate")
def course_integral_symbolic_yoga_associate():
    return render_template("integral_symbolic_yoga.html")

@app.route("/trainings/integral-symbolic-yoga/practitioner")
def course_integral_symbolic_yoga_practitioner():
    return render_template("integral_symbolic_yoga.html")

@app.route("/trainings/integral-symbolic-yoga/master")
def course_integral_symbolic_yoga_master():
    return render_template("integral_symbolic_yoga.html")

# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)