import os
import json
import sqlite3
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for, g
from werkzeug.security import check_password_hash, generate_password_hash

from services.ai_service import evaluate_answer
from services.scoring import calculate_overall_score

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-secret-key")
app.config["DATABASE"] = os.getenv("DATABASE_PATH", "instance/interview.db")
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        question_text TEXT NOT NULL,
        reference_answer TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        category TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        overall_score REAL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        answer_text TEXT NOT NULL,
        score REAL NOT NULL,
        feedback TEXT NOT NULL,
        strengths TEXT NOT NULL,
        improvements TEXT NOT NULL,
        suggested_answer TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY(question_id) REFERENCES questions(id)
    );
    """)
    count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if count == 0:
        seed = [
            ("Python", "Easy", "What is a Python dictionary?", "A dictionary is a mutable mapping that stores key-value pairs. Keys are unique and values are accessed using keys."),
            ("Python", "Medium", "What is the difference between a list and a tuple?", "A list is mutable and uses square brackets. A tuple is immutable and commonly uses parentheses. Both can store ordered collections."),
            ("Python", "Medium", "What is exception handling in Python?", "Exception handling uses try and except to handle runtime errors. finally can run cleanup code and else can run when no exception occurs."),
            ("Data Analytics", "Easy", "What is the difference between mean and median?", "Mean is the arithmetic average. Median is the middle value after sorting; it is less affected by extreme outliers."),
            ("Data Analytics", "Medium", "Why is data cleaning important?", "Data cleaning identifies and fixes missing, duplicated, inconsistent, or invalid data so analysis is more reliable."),
            ("SQL", "Easy", "What is a primary key?", "A primary key uniquely identifies each row in a table and must be unique and non-null."),
            ("HR", "Easy", "Tell me about yourself.", "Give a concise professional introduction covering education or experience, relevant skills, an example or achievement, and the role you are seeking."),
            ("HR", "Medium", "Describe a challenge you faced and how you handled it.", "Use a structured example: situation, task, action, and result. Explain your contribution and what you learned."),
            ("General", "Medium", "Why should we hire you?", "Connect relevant skills and evidence of learning or achievement to the role, and explain the value you can bring.")
        ]
        db.executemany(
            "INSERT INTO questions(category, difficulty, question_text, reference_answer) VALUES (?, ?, ?, ?)",
            seed
        )
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and use a password with at least 8 characters.", "error")
            return render_template("register.html")
        try:
            db = get_db()
            db.execute(
                "INSERT INTO users(name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), datetime.utcnow().isoformat(timespec="seconds"))
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("register.html")
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    interviews = db.execute(
        "SELECT * FROM interviews WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,)
    ).fetchall()
    stats = db.execute(
        """SELECT COUNT(*) AS total, AVG(overall_score) AS average
           FROM interviews WHERE user_id = ? AND completed_at IS NOT NULL""",
        (user_id,)
    ).fetchone()
    categories = db.execute(
        "SELECT DISTINCT category FROM questions ORDER BY category"
    ).fetchall()
    return render_template("dashboard.html", interviews=interviews, stats=stats, categories=categories)


@app.route("/interview/start", methods=["POST"])
@login_required
def start_interview():
    category = request.form.get("category", "Python").strip()
    role = request.form.get("role", "General candidate").strip()[:100] or "General candidate"
    db = get_db()
    questions = db.execute(
        "SELECT id FROM questions WHERE category = ? ORDER BY RANDOM() LIMIT 5", (category,)
    ).fetchall()
    if not questions:
        flash("No questions found for that category yet.", "error")
        return redirect(url_for("dashboard"))
    cursor = db.execute(
        "INSERT INTO interviews(user_id, role, category, started_at) VALUES (?, ?, ?, ?)",
        (session["user_id"], role, category, datetime.utcnow().isoformat(timespec="seconds"))
    )
    interview_id = cursor.lastrowid
    db.commit()
    session["current_interview_id"] = interview_id
    session["question_ids"] = [q["id"] for q in questions]
    session["question_index"] = 0
    return redirect(url_for("interview_question"))


@app.route("/interview/question", methods=["GET", "POST"])
@login_required
def interview_question():
    interview_id = session.get("current_interview_id")
    question_ids = session.get("question_ids", [])
    index = session.get("question_index", 0)
    if not interview_id or not question_ids:
        flash("Start an interview to begin.", "warning")
        return redirect(url_for("dashboard"))
    db = get_db()
    interview = db.execute(
        "SELECT * FROM interviews WHERE id = ? AND user_id = ?",
        (interview_id, session["user_id"])
    ).fetchone()
    if not interview:
        session.pop("current_interview_id", None)
        flash("Interview session not found.", "error")
        return redirect(url_for("dashboard"))
    if index >= len(question_ids):
        return redirect(url_for("finish_interview"))
    question = db.execute("SELECT * FROM questions WHERE id = ?", (question_ids[index],)).fetchone()

    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        if not answer:
            flash("Please enter an answer before continuing.", "error")
            return render_template("interview.html", question=question, index=index + 1, total=len(question_ids), interview=interview)
        if len(answer) > 10000:
            flash("Please keep your answer under 10,000 characters.", "error")
            return render_template("interview.html", question=question, index=index + 1, total=len(question_ids), interview=interview)

        evaluation = evaluate_answer(
            question=question["question_text"],
            answer=answer,
            reference_answer=question["reference_answer"],
            category=question["category"]
        )
        db.execute(
            """INSERT INTO answers(interview_id, question_id, answer_text, score, feedback,
               strengths, improvements, suggested_answer, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                interview_id, question["id"], answer, evaluation["score"], evaluation["feedback"],
                json.dumps(evaluation["strengths"]), json.dumps(evaluation["improvements"]),
                evaluation["suggested_answer"], datetime.utcnow().isoformat(timespec="seconds")
            )
        )
        db.commit()
        session["last_evaluation"] = evaluation
        session["last_question"] = question["question_text"]
        session["last_answer"] = answer
        session["question_index"] = index + 1
        return redirect(url_for("answer_feedback"))

    return render_template("interview.html", question=question, index=index + 1, total=len(question_ids), interview=interview)


@app.route("/interview/feedback")
@login_required
def answer_feedback():
    evaluation = session.get("last_evaluation")
    if not evaluation:
        return redirect(url_for("dashboard"))
    return render_template(
        "feedback.html", evaluation=evaluation,
        question=session.get("last_question", ""),
        answer=session.get("last_answer", ""),
        has_next=session.get("question_index", 0) < len(session.get("question_ids", []))
    )


@app.route("/interview/next", methods=["POST"])
@login_required
def next_question():
    return redirect(url_for("interview_question"))


@app.route("/interview/finish")
@login_required
def finish_interview():
    interview_id = session.get("current_interview_id")
    if not interview_id:
        return redirect(url_for("dashboard"))
    db = get_db()
    interview = db.execute(
        "SELECT * FROM interviews WHERE id = ? AND user_id = ?",
        (interview_id, session["user_id"])
    ).fetchone()
    if not interview:
        session.pop("current_interview_id", None)
        return redirect(url_for("dashboard"))
    scores = db.execute("SELECT score FROM answers WHERE interview_id = ?", (interview_id,)).fetchall()
    overall = calculate_overall_score([row["score"] for row in scores])
    db.execute(
        "UPDATE interviews SET completed_at = ?, overall_score = ? WHERE id = ?",
        (datetime.utcnow().isoformat(timespec="seconds"), overall, interview_id)
    )
    db.commit()
    answers = db.execute(
        """SELECT answers.*, questions.question_text, questions.category
           FROM answers JOIN questions ON answers.question_id = questions.id
           WHERE answers.interview_id = ? ORDER BY answers.id""",
        (interview_id,)
    ).fetchall()
    session.pop("current_interview_id", None)
    session.pop("question_ids", None)
    session.pop("question_index", None)
    session.pop("last_evaluation", None)
    return render_template("report.html", interview=interview, overall=overall, answers=answers)


@app.route("/history")
@login_required
def history():
    rows = get_db().execute(
        """SELECT i.*, COUNT(a.id) AS answer_count
           FROM interviews i LEFT JOIN answers a ON a.interview_id = i.id
           WHERE i.user_id = ?
           GROUP BY i.id ORDER BY i.id DESC""",
        (session["user_id"],)
    ).fetchall()
    return render_template("history.html", interviews=rows)


@app.route("/health")
def health():
    return {"status": "ok"}


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
