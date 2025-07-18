from flask import Blueprint, request, session, redirect, url_for, render_template, flash, send_file
from datetime import datetime, date
import psycopg2
import psycopg2.extras
from db import get_db_connection
import io
import pandas as pd

attendance_bp = Blueprint("attendance", __name__)

# 출근 등록
@attendance_bp.route("/attendance/clock_in", methods=["POST"])
def clock_in():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    today = date.today()
    memo_in = request.form.get("memo_in", "").strip()
    xff = request.headers.get('X-Forwarded-For')
    ip_address = xff.split(',')[0].strip() if xff else request.remote_addr

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
            """
            INSERT INTO attendance (user_name, work_date, clock_in, memo_in, ip_address_in)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user["name"], today, datetime.now(), memo_in, ip_address)
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
    xff = request.headers.get('X-Forwarded-For')
    ip_address = xff.split(',')[0].strip() if xff else request.remote_addr

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE attendance
        SET clock_out = %s, memo_out = %s, ip_address_out = %s
        WHERE user_name = %s AND work_date = %s AND clock_out IS NULL
    """, (datetime.now(), memo_out, ip_address, user["name"], today))

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
        SELECT id, work_date, clock_in, clock_out, memo_in, memo_out, ip_address_in, ip_address_out
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


def create_attendance_table():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 기존 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            user_name TEXT NOT NULL,
            work_date DATE NOT NULL,
            clock_in TIMESTAMP,
            clock_out TIMESTAMP,
            memo_in TEXT,
            memo_out TEXT
        );
    """)
    
    # IP 칼럼이 없으면 추가
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='attendance'")
    existing_columns = [row[0] for row in cursor.fetchall()]

    if "ip_address_in" not in existing_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN ip_address_in TEXT;")
    if "ip_address_out" not in existing_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN ip_address_out TEXT;")

    conn.commit()
    conn.close()


@attendance_bp.route("/attendance/download")
def download_attendance():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT work_date AS "날짜",
               clock_in AS "출근 시간",
               clock_out AS "퇴근 시간",
               memo_in AS "출근 메모",
               memo_out AS "퇴근 메모",
               ip_address_in AS "출근 IP",
               ip_address_out AS "퇴근 IP"
        FROM attendance
        WHERE user_name = %s
        ORDER BY work_date DESC
    """, (user["name"],))
    records = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(records)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="attendance_records.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
