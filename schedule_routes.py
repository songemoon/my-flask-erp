from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, abort
import hashlib
import psycopg2
import psycopg2.extras
from db import get_db_connection

schedule_bp = Blueprint("schedule", __name__)

@schedule_bp.route("/schedule/add", methods=["GET", "POST"])
def add_schedule():
    if request.method == "POST":
        title = request.form["title"]
        start = request.form["start"]
        end_time = request.form["end_time"]
        schedule_type = request.form["type"]

        user = session.get("user")
        employee_name = user["name"] if user else request.form.get("employee_name")
        password = request.form.get("password")
        password_hash = hashlib.sha256(password.encode()).hexdigest() if not user and password else None

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                start TEXT NOT NULL,
                end_time TEXT,
                type TEXT NOT NULL,
                employee_name TEXT,
                username TEXT,
                password TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO schedules (title, start, end_time, type, employee_name, username, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (title, start, end_time, schedule_type, employee_name, user["username"] if user else None, password_hash))

        conn.commit()
        conn.close()
        return redirect(url_for("schedule.view_calendar"))

    return render_template("add_schedule.html")


@schedule_bp.route("/api/schedules")
def api_get_schedules():
    employee = request.args.get("employee")
    schedule_type = request.args.get("type")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    query = "SELECT * FROM schedules WHERE TRUE"
    params = []

    if employee:
        query += " AND employee_name = %s"
        params.append(employee)

    if schedule_type:
        query += " AND type = %s"
        params.append(schedule_type)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "title": f"{row['title']} ({row['employee_name']})",
            "start": row["start"],
            "end_time": row["end_time"],
            "color": "#ADD8E6" if row["type"] == "휴가" else "#FFD700"
        })

    return jsonify(result)


@schedule_bp.route("/calendar")
def view_calendar():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT employee_name FROM schedules WHERE employee_name IS NOT NULL")
    employees = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template("calendar.html", employees=employees)


@schedule_bp.route("/schedule/edit/<int:schedule_id>", methods=["GET", "POST"])
def edit_schedule(schedule_id):
    user = session.get("user")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM schedules WHERE id = %s", (schedule_id,))
    schedule = cursor.fetchone()

    if not schedule:
        conn.close()
        return "일정을 찾을 수 없습니다.", 404

    if request.method == "POST":
        if user:
            if schedule["employee_name"] and schedule["employee_name"] != user.get("name"):
                conn.close()
                return abort(403)
        else:
            password_input = request.form.get("password")
            password_hash = hashlib.sha256(password_input.encode()).hexdigest()
            if password_hash != schedule["password"]:
                conn.close()
                return "비밀번호가 일치하지 않습니다.", 403

        title = request.form["title"]
        start = request.form["start"]
        end_time = request.form["end_time"]
        schedule_type = request.form["type"]

        cursor.execute("""
            UPDATE schedules
            SET title = %s, start = %s, end_time = %s, type = %s
            WHERE id = %s
        """, (title, start, end_time, schedule_type, schedule_id))
        conn.commit()
        conn.close()
        return redirect(url_for("schedule.view_calendar"))

    conn.close()
    return render_template("edit_schedule.html", schedule=schedule)


@schedule_bp.route("/schedule/delete/<int:schedule_id>", methods=["GET", "POST"])
def delete_schedule(schedule_id):
    user = session.get("user")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM schedules WHERE id = %s", (schedule_id,))
    schedule = cursor.fetchone()

    if not schedule:
        conn.close()
        return "일정을 찾을 수 없습니다.", 404

    if request.method == "POST":
        if user:
            if schedule["employee_name"] and schedule["employee_name"] != user.get("name"):
                conn.close()
                return abort(403)
        else:
            password_input = request.form.get("password")
            password_hash = hashlib.sha256(password_input.encode()).hexdigest()
            if password_hash != schedule["password"]:
                conn.close()
                return "비밀번호가 일치하지 않습니다.", 403

        cursor.execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))
        conn.commit()
        conn.close()
        return redirect(url_for("schedule.view_calendar"))

    conn.close()
    return render_template("confirm_delete.html", schedule=schedule)

def create_schedule_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            start TEXT NOT NULL,
            end_time TEXT,
            type TEXT NOT NULL,
            employee_name TEXT,
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()
