import sqlite3
from flask import request, render_template, redirect, url_for
from common import COUNTRY_CODE_MAP



def manage_suppliers():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"].strip()
        country_name = request.form["country"].strip()
        country_code = COUNTRY_CODE_MAP.get(country_name)

        if not name or not country_code:
            conn.close()
            # 오류 메시지와 함께 GET 요청으로 리디렉션
            return redirect(url_for("manage_suppliers", error="입력값이 부족하거나 국가 선택이 잘못되었습니다."))

        try:
            code = generate_supplier_code(country_code)
            cursor.execute("""
                INSERT INTO suppliers (code, name, country_code)
                VALUES (?, ?, ?)
            """, (code, name, country_code))
            conn.commit()
            conn.close()
            # 성공 메시지와 함께 목록 페이지로 리디렉션
            return redirect(url_for("manage_suppliers", success="거래처가 성공적으로 등록되었습니다."))
        except Exception as e:
            conn.close()
            return redirect(url_for("manage_suppliers", error=f"등록 중 오류 발생: {str(e)}"))

    # GET 요청: 목록 조회 및 메시지 표시
    success = request.args.get("success")
    error = request.args.get("error")

    cursor.execute("SELECT * FROM suppliers ORDER BY country_code, code")
    suppliers = cursor.fetchall()
    conn.close()

    return render_template(
        "manage_suppliers.html",
        suppliers=suppliers,
        countries=COUNTRY_CODE_MAP,
        success=success,
        error=error
    )


def create_supplier_table():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            country_code TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def generate_supplier_code(country_code):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM suppliers WHERE country_code = ?
    """, (country_code,))
    count = cursor.fetchone()[0]
    conn.close()

    return f"{country_code}{count + 1:02d}"  # 예: KR01, KR02


def delete_supplier(supplier_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("list_suppliers"))