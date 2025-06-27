from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from datetime import datetime, date
import psycopg2
import psycopg2.extras
from db import get_db_connection

attendance_bp = Blueprint("attendance", __name__)

# 출근 등록
@attendance_bp.route("/attendance/clock_in", methods=["POST"])
def clock_in():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    today = date.today()
    memo_in = request.form.get("memo_in", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM attendance WHERE user_name = %s AND work_date = %s",
        (user["name"], today)
    )
    exists = cursor.fetchone()

    if exists:
        flash("이미 출근 등록이 완료되었습니다.")
    else:
        cursor.execute(
            "INSERT INTO attendance (user_name, work_date, clock_in, memo_in) VALUES (%s, %s, %s, %s)",
            (user["name"], today, datetime.now(), memo_in)
        )
        conn.commit()
        flash("✅ 출근 등록 완료")

    conn.close()
    return redirect(url_for("home"))


# 퇴근 등록
@attendance_bp.route("/attendance/clock_out", methods=["POST"])
def clock_out():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    today = date.today()
    memo_out = request.form.get("memo_out", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE attendance
        SET clock_out = %s, memo_out = %s
        WHERE user_name = %s AND work_date = %s AND clock_out IS NULL
    """, (datetime.now(), memo_out, user["name"], today))

    if cursor.rowcount > 0:
        conn.commit()
        flash("✅ 퇴근 등록 완료")
    else:
        flash("❌ 출근 기록이 없거나 이미 퇴근 처리되었습니다.")

    conn.close()
    return redirect(url_for("home"))


# 근태 로그 페이지
@attendance_bp.route("/attendance")
def attendance_dashboard():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT work_date, clock_in, clock_out, memo_in, memo_out
        FROM attendance
        WHERE user_name = %s
        ORDER BY work_date DESC
        LIMIT 30
    """, (user["name"],))
    records = cursor.fetchall()
    conn.close()

    return render_template("attendance_dashboard.html", records=records)


@attendance_bp.route("/attendance/delete/<int:attendance_id>", methods=["POST"])
def delete_attendance(attendance_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM attendance
            WHERE id = %s AND user_name = %s
        """, (attendance_id, user["name"]))
        conn.commit()
        flash("✅ 근태 기록이 삭제되었습니다.")
    except Exception as e:
        conn.rollback()
        flash(f"❌ 삭제 중 오류 발생: {e}")
    finally:
        conn.close()

    return redirect(url_for("attendance.attendance_dashboard"))
