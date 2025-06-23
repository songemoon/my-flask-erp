import psycopg2.extras
from flask import request, render_template, redirect, url_for
from db import get_db_connection

def register_cost(order_code):
    if request.method == "POST":
        # 🔹 공통비용 계산
        expense_names = request.form.getlist("expense_name")
        expense_amounts = request.form.getlist("expense_amount")
        try:
            total_amount = sum(float(e) for e in expense_amounts if e.strip())
        except ValueError:
            return "❌ 공통비용 입력값 중 숫자가 아닌 항목이 있습니다."

        items = []
        total_qty = 0
        idx = 0

        while True:
            sku = request.form.get(f"sku_{idx}")
            qty = request.form.get(f"qty_{idx}")
            price = request.form.get(f"unit_price_{idx}")
            if not sku:
                break

            try:
                qty = int(qty)
                price = float(price)
            except:
                return f"❌ #{idx+1}번 항목의 수량 또는 단가 형식 오류"

            total_qty += qty
            items.append({
                "sku": sku,
                "qty": qty,
                "unit_price": price
            })
            idx += 1

        if total_qty == 0:
            return "❌ 총 수량이 0입니다."

        common_unit_cost = round(total_amount / total_qty, 4) if total_amount else 0

        # 👉 DB 저장
        conn = get_db_connection()
        cursor = conn.cursor()

        # 기존 데이터 삭제
        cursor.execute("DELETE FROM cost_history WHERE order_code = ?", (order_code,))
        cursor.execute("DELETE FROM cost_expense WHERE order_code = ?", (order_code,))

        # 원가 저장
        for item in items:
            final_cost = round(item["unit_price"] + common_unit_cost, 4)
            cursor.execute("""
                INSERT INTO cost_history (
                    order_code, sku, quantity, unit_price,
                    common_unit_cost, final_cost
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_code, item["sku"], item["qty"],
                item["unit_price"], common_unit_cost, final_cost
            ))

        # 공통비용 저장
        for name, amount in zip(expense_names, expense_amounts):
            if name.strip() and amount.strip():
                cursor.execute("""
                    INSERT INTO cost_expense (order_code, expense_name, expense_amount)
                    VALUES (?, ?, ?)
                """, (order_code, name.strip(), float(amount.strip())))

        conn.commit()
        conn.close()

        # 🔁 새로 저장된 데이터 다시 로딩 (화면에 반영)
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,))
        order_items = cursor.fetchall()
        conn.close()

        message = f"✅ 원가 등록 완료! 배분 단가: {common_unit_cost} €"
        return render_template(
            "register_cost.html",
            items=order_items,
            cost_items={item["sku"]: item for item in items},
            order_code=order_code,
            expense_items=[{"expense_name": n, "expense_amount": a} for n, a in zip(expense_names, expense_amounts)],
            message=message
        )

    # GET 요청
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,))
    order_items = cursor.fetchall()

    cursor.execute("SELECT * FROM cost_history WHERE order_code = ?", (order_code,))
    cost_items = {row["sku"]: dict(row) for row in cursor.fetchall()}

    cursor.execute("SELECT * FROM cost_expense WHERE order_code = ?", (order_code,))
    expense_items = cursor.fetchall()
    conn.close()

    return render_template(
        "register_cost.html",
        items=order_items,
        cost_items=cost_items,
        order_code=order_code,
        expense_items=expense_items
    )



def view_cost_history():
    query = request.args.get("q", "").strip()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 제품 정보 가져오기 (이름/바코드 조회를 위해)
    base_sql = """
        SELECT c.*, p.name AS product_name, p.barcode
        FROM cost_history c
        LEFT JOIN products p ON c.sku = p.sku
        WHERE 1=1
    """
    params = []

    if query:
        base_sql += """
            AND (
                c.sku LIKE ?
                OR p.name LIKE ?
                OR p.barcode LIKE ?
                OR c.order_code LIKE ?
            )
        """
        q_like = f"%{query}%"
        params.extend([q_like, q_like, q_like, q_like])

    base_sql += " ORDER BY c.sku ASC, c.timestamp DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    # SKU별로 그룹화
    grouped = {}
    for row in rows:
        sku = row["sku"]
        if sku not in grouped:
            grouped[sku] = []
        grouped[sku].append(row)

    return render_template("cost_history.html", query=query, grouped=grouped)


def create_cost_history_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            common_unit_cost REAL NOT NULL,
            final_cost REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def create_cost_expense_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_expense (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT NOT NULL,
            expense_name TEXT NOT NULL,
            expense_amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def initialize_cost_expense_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_expense (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT,
            expense_name TEXT,
            expense_amount REAL
        )
    """)
    conn.commit()
    conn.close()