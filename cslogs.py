from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from db import get_db_connection

cslogs_bp = Blueprint("cslogs", __name__)

@cslogs_bp.route("/cs_logs/register", methods=["GET", "POST"])
def register_cs_log():
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        product_name = request.form.get("product_name", "").strip()
        log_type = request.form.get("log_type", "").strip()
        quantity = request.form.get("quantity", "").strip()
        reason = request.form.get("reason", "").strip()
        location = request.form.get("location", "").strip()
        created_by = session.get("user", "")
        created_at = datetime.now()

        if not sku or not log_type or not quantity:
            flash("❌ 필수 항목이 누락되었습니다.")
            return redirect(url_for("cslogs.register_cs_log"))

        try:
            quantity = int(quantity)
        except ValueError:
            flash("❌ 수량은 숫자로 입력해야 합니다.")
            return redirect(url_for("cslogs.register_cs_log"))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cs_logs (sku, product_name, log_type, quantity, reason, location, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (sku, product_name, log_type, quantity, reason, location, created_by, created_at))
        conn.commit()
        conn.close()

        flash("✅ CS 로그가 등록되었습니다.")
        return redirect(url_for("cslogs.register_cs_log"))

    return render_template("register_cs_log.html")


@cslogs_bp.route("/cs_logs")
def view_cs_logs():
    query = request.args.get("q", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT id, created_at, sku, product_name, log_type, quantity, reason, location, created_by FROM cs_logs"
    params = []

    if query:
        sql += " WHERE sku ILIKE %s OR product_name ILIKE %s"
        params.extend([f"%{query}%", f"%{query}%"])

    sql += " ORDER BY created_at DESC"

    cursor.execute(sql, params)
    logs = cursor.fetchall()
    conn.close()

    return render_template("cs_logs.html", logs=logs, query=query)




@cslogs_bp.route("/cs_logs/edit/<int:log_id>", methods=["GET", "POST"])
def edit_cs_log(log_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "POST":
        data = {
            "log_type": request.form.get("log_type", ""),
            "quantity": int(request.form.get("quantity", "0")),
            "reason": request.form.get("reason", "").strip(),
            "location": request.form.get("location", "")
        }

        cursor.execute("""
            UPDATE cs_logs
            SET log_type = %(log_type)s,
                quantity = %(quantity)s,
                reason = %(reason)s,
                location = %(location)s
            WHERE id = %s
        """, (data["log_type"], data["quantity"], data["reason"], data["location"], log_id))
        conn.commit()
        conn.close()
        flash("✅ 로그가 수정되었습니다.")
        return redirect(url_for("cslogs.view_cs_logs"))

    cursor.execute("SELECT * FROM cs_logs WHERE id = %s", (log_id,))
    log = cursor.fetchone()
    conn.close()
    return render_template("edit_cs_log.html", log=log)


