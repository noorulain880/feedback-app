"""
Feedback Board - a three-tier app for the DevOps lab mid exam.
Front-end: templates/index.html, templates/edit.html
Back-end:  this Flask app  (validation, create / read / update / delete,
                            helpful votes, sorting, rating-by-course stats)
Database:  MySQL, running in its own container
"""
import os
import time
import pymysql
from flask import Flask, render_template, request, redirect, url_for, abort

app = Flask(__name__)

DB_HOST = os.environ.get("DB_HOST", "db")
DB_USER = os.environ.get("DB_USER", "feedback_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "feedback_pass")
DB_NAME = os.environ.get("DB_NAME", "feedback_db")

CATEGORIES = ["Bug", "Suggestion", "Praise", "Other"]
COURSES = [
    "DevOps",
    "Cloud Computing",
    "Web Engineering",
    "Database Systems",
    "Software Engineering",
]
RATINGS = [1, 2, 3, 4, 5]
MAX_NAME = 50
MIN_MESSAGE = 5
MAX_MESSAGE = 300

# key -> (label shown in dropdown, ORDER BY clause). Whitelisted, so it is
# safe to put the clause into the query string.
SORTS = {
    "newest": ("Newest first", "id DESC"),
    "oldest": ("Oldest first", "id ASC"),
    "rating": ("Highest rating", "rating DESC, id DESC"),
    "helpful": ("Most helpful", "helpful DESC, id DESC"),
}
DEFAULT_SORT = "newest"

# Columns added by newer versions of the app (used for the migration).
NEW_COLUMNS = {
    "category": "VARCHAR(20) NOT NULL DEFAULT 'Other'",
    "course": "VARCHAR(50) NOT NULL DEFAULT 'DevOps'",
    "rating": "TINYINT NOT NULL DEFAULT 3",
    "helpful": "INT NOT NULL DEFAULT 0",
}


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_db():
    """Create the table, and add any missing columns if the table already
    existed from an older version of the app. Retries because the db
    container may still be starting."""
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
                        category VARCHAR(20) NOT NULL DEFAULT 'Other',
                        course VARCHAR(50) NOT NULL DEFAULT 'DevOps',
                        rating TINYINT NOT NULL DEFAULT 3,
                        helpful INT NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                # Migration for databases created by older versions.
                cur.execute(
                    "SELECT column_name AS col FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = 'feedback'",
                    (DB_NAME,),
                )
                existing = {row["col"].lower() for row in cur.fetchall()}
                for column, definition in NEW_COLUMNS.items():
                    if column not in existing:
                        cur.execute(
                            f"ALTER TABLE feedback ADD COLUMN {column} {definition}"
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


def parse_rating(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate(name, message, category, course, rating):
    """Return an error string, or None if the input is valid."""
    if not name or not message:
        return "Both name and message are required."
    if len(name) > MAX_NAME:
        return f"Name must be at most {MAX_NAME} characters."
    if len(message) < MIN_MESSAGE:
        return f"Message must be at least {MIN_MESSAGE} characters."
    if len(message) > MAX_MESSAGE:
        return f"Message must be at most {MAX_MESSAGE} characters."
    if course not in COURSES:
        return "Please choose a valid course."
    if category not in CATEGORIES:
        return "Please choose a valid category."
    if rating not in RATINGS:
        return "Please choose a rating from 1 to 5."
    return None


def clean_state(category, sort):
    """Make sure the filter and sort values coming from the URL are valid."""
    category = category if category in CATEGORIES else ""
    sort = sort if sort in SORTS else DEFAULT_SORT
    return category, sort


def redirect_to_list(category, sort):
    category, sort = clean_state(category, sort)
    args = {}
    if category:
        args["category"] = category
    if sort != DEFAULT_SORT:
        args["sort"] = sort
    return redirect(url_for("index", **args))


def load_entries(selected, sort):
    """Return (entries, counts) for the list page."""
    order_by = SORTS[sort][1]
    conn = get_connection()
    with conn.cursor() as cur:
        columns = "id, name, message, category, course, rating, helpful, created_at"
        if selected in CATEGORIES:
            cur.execute(
                f"SELECT {columns} FROM feedback "
                f"WHERE category = %s ORDER BY {order_by}",
                (selected,),
            )
        else:
            cur.execute(f"SELECT {columns} FROM feedback ORDER BY {order_by}")
        entries = cur.fetchall()
        cur.execute("SELECT category, COUNT(*) AS c FROM feedback GROUP BY category")
        counts = {row["category"]: row["c"] for row in cur.fetchall()}
    conn.close()
    return entries, counts


def load_chart():
    """Average rating and entry count for every course (all entries)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT course, AVG(rating) AS avg_rating, COUNT(*) AS c "
            "FROM feedback GROUP BY course"
        )
        rows = {row["course"]: row for row in cur.fetchall()}
    conn.close()

    chart = []
    for course in COURSES:
        row = rows.get(course)
        avg = float(row["avg_rating"]) if row else 0.0
        chart.append(
            {
                "course": course,
                "avg": round(avg, 2),
                "count": row["c"] if row else 0,
                "pct": round(avg / 5 * 100),
            }
        )
    return chart


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    form = {
        "name": "",
        "message": "",
        "category": CATEGORIES[0],
        "course": COURSES[0],
        "rating": 5,
    }
    selected, sort = clean_state(
        request.args.get("category", ""), request.args.get("sort", "")
    )

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        message = request.form.get("message", "").strip()
        category = request.form.get("category", "")
        course = request.form.get("course", "")
        rating = parse_rating(request.form.get("rating", ""))
        form = {
            "name": name,
            "message": message,
            "category": category,
            "course": course,
            "rating": rating,
        }

        error = validate(name, message, category, course, rating)
        if error is None:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO feedback (name, message, category, course, rating) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (name, message, category, course, rating),
                )
            conn.commit()
            conn.close()
            return redirect(url_for("index"))

    entries, counts = load_entries(selected, sort)
    total = sum(counts.values())
    return render_template(
        "index.html",
        entries=entries,
        error=error,
        form=form,
        categories=CATEGORIES,
        courses=COURSES,
        ratings=RATINGS,
        counts=counts,
        total=total,
        selected=selected,
        sort=sort,
        sort_arg=sort if sort != DEFAULT_SORT else None,
        sorts=[(key, label) for key, (label, _) in SORTS.items()],
        chart=load_chart(),
        max_name=MAX_NAME,
        max_message=MAX_MESSAGE,
    )


@app.route("/edit/<int:entry_id>", methods=["GET", "POST"])
def edit(entry_id):
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        message = request.form.get("message", "").strip()
        category = request.form.get("category", "")
        course = request.form.get("course", "")
        rating = parse_rating(request.form.get("rating", ""))
        form = {
            "name": name,
            "message": message,
            "category": category,
            "course": course,
            "rating": rating,
        }

        error = validate(name, message, category, course, rating)
        if error is None:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE feedback SET name = %s, message = %s, category = %s, "
                    "course = %s, rating = %s WHERE id = %s",
                    (name, message, category, course, rating, entry_id),
                )
            conn.commit()
            conn.close()
            return redirect(url_for("index"))
    else:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, message, category, course, rating "
                "FROM feedback WHERE id = %s",
                (entry_id,),
            )
            row = cur.fetchone()
        conn.close()
        if row is None:
            abort(404)
        form = row

    return render_template(
        "edit.html",
        entry_id=entry_id,
        error=error,
        form=form,
        categories=CATEGORIES,
        courses=COURSES,
        max_name=MAX_NAME,
        max_message=MAX_MESSAGE,
    )


@app.route("/helpful/<int:entry_id>", methods=["POST"])
def helpful(entry_id):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE feedback SET helpful = helpful + 1 WHERE id = %s", (entry_id,)
        )
    conn.commit()
    conn.close()
    return redirect_to_list(request.form.get("back", ""), request.form.get("sort", ""))


@app.route("/delete/<int:entry_id>", methods=["POST"])
def delete(entry_id):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM feedback WHERE id = %s", (entry_id,))
    conn.commit()
    conn.close()
    return redirect_to_list(request.form.get("back", ""), request.form.get("sort", ""))


@app.route("/health")
def health():
    # Endpoint the Load Balancer's health check calls.
    return "OK", 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)