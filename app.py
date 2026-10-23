"""
Feedback Board — a minimal three-tier app for the DevOps lab mid exam.
Front-end: templates/index.html (one page: a form + a list)
Back-end:  this Flask app
Database:  MySQL, running in its own container
"""
import os
import time
import pymysql
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

DB_HOST = os.environ.get("DB_HOST", "db")
DB_USER = os.environ.get("DB_USER", "feedback_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "feedback_pass")
DB_NAME = os.environ.get("DB_NAME", "feedback_db")


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_db():
    """Create the feedback table if it doesn't exist yet.
    Retries for a bit because the db container may still be starting
    when this container first comes up."""
    last_error = None
    for attempt in range(15):
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            conn.commit()
            conn.close()
            print("Database ready.")
            return
        except Exception as e:
            last_error = e
            print(f"DB not ready yet (attempt {attempt + 1}/15): {e}")
            time.sleep(3)
    raise RuntimeError(f"Could not connect to database: {last_error}")


@app.route("/", methods=["GET", "POST"])
def index():
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not message:
            error = "Both name and message are required."
        else:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO feedback (name, message) VALUES (%s, %s)",
                    (name, message),
                )
            conn.commit()
            conn.close()
            return redirect(url_for("index"))

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT name, message, created_at FROM feedback ORDER BY id DESC")
        entries = cur.fetchall()
    conn.close()

    return render_template("index.html", entries=entries, error=error)


@app.route("/health")
def health():
    # Simple endpoint the Load Balancer's health check can hit.
    return "OK", 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)