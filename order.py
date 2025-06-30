from flask import request, render_template, redirect, url_for, session
from datetime import datetime, timedelta, date
import psycopg2
import psycopg2.extras
from db import get_db_connection
from inventory import safe_int


def new_order():
    user = session.get("user")
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        supplier_id = request.form.get("supplier_id")

        # 다중 제품 처리
        products = []
        idx = 0
        while True:
            pname = request.form.get(f"product_name_{idx}")
            psku = request.form.get(f"product_sku_{idx}")
            pqty = request.form.get(f"quantity_{idx}")
            if pname is None or pqty is None:
                break
            if pname and pqty.isdigit() and int(pqty) > 0:
                products.append((psku, pname, int(pqty)))
            idx += 1

        if not products:
            return "제품명과 수량을 최소 1개 입력하세요.", 400

        order_code = generate_order_code()
        order_date = datetime.today().strftime("%Y-%m-%d")
        staff_name = user["name"]
        staff_english_name = user.get("english_name", "")
        cursor.execute("SELECT name FROM suppliers WHERE id = %s", (supplier_id,))
        row = cursor.fetchone()
        if row:
            supplier_name = row["name"]
        else:
            supplier_name = "알수없음"

        inquiry = request.form.get("inquiry", "")

        for sku, name, qty in products:
            cursor.execute("""
                INSERT INTO orders (
                    order_code, supplier_id, supplier_name,
                    product_sku, product_name, quantity,
                    inquiry, order_date, staff_name, staff_english_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                order_code, supplier_id, supplier_name,
                sku, name, qty,
                inquiry, order_date, staff_name, staff_english_name  # 여기에 추가
            ))

        conn.commit()
        conn.close()
        return redirect(url_for("view_order", order_code=order_code))

    # ✅ GET 요청 처리
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = cursor.fetchall()
    conn.close()

    order_code = None
    return render_template("new_order.html", suppliers=suppliers, user=user, order_code=order_code)

def list_orders():
    query = request.args.get("q", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    base_sql = """
        SELECT 
            o.order_code,
            o.supplier_id,
            s.code AS supplier_code,
            o.supplier_name,
            o.inquiry,
            o.order_date,
            o.staff_name,
            COUNT(*) AS item_count
        FROM orders o
        LEFT JOIN suppliers s ON o.supplier_id = s.id
    """

    params = []
    if query:
        like_query = f"%{query}%"
        base_sql += """
            WHERE o.order_code ILIKE %s
            OR o.supplier_name ILIKE %s
            OR CAST(o.supplier_id AS TEXT) ILIKE %s
            OR o.staff_name ILIKE %s
        """
        params = [like_query, like_query, like_query, like_query]

    base_sql += " GROUP BY o.order_code, o.supplier_id, s.code, o.supplier_name, o.inquiry, o.order_date, o.staff_name ORDER BY o.order_date DESC"

    cursor.execute(base_sql, params)
    orders = cursor.fetchall()
    conn.close()

    return render_template("list_orders.html", orders=orders, query=query)

def view_order(order_code):
    user = session.get("user")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("""
        SELECT 
            o.order_code,
            o.order_date,
            o.inquiry,
            o.quantity,
            o.product_sku,
            o.staff_name,
            p.english_name,
            p.name AS product_name,
            s.name AS supplier_name
        FROM orders o
        JOIN products p ON o.product_sku = p.sku
        JOIN suppliers s ON o.supplier_id = s.id
        WHERE o.order_code = %s
    """, (order_code,))

    items = cursor.fetchall()
    conn.close()

    if not items:
        return "발주서가 없습니다.", 404

    return render_template("view_order.html", items=items, order_code=order_code, user=user)

def edit_order(order_code):
    user = session.get("user")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id")
        inquiry = request.form.get("inquiry", "")

        # 제품 목록 수집
        products = []
        idx = 0
        while True:
            pname = request.form.get(f"product_name_{idx}")
            psku = request.form.get(f"product_sku_{idx}")
            pqty = request.form.get(f"quantity_{idx}")
            if pname is None or pqty is None:
                break
            if pname and pqty.isdigit() and int(pqty) > 0:
                products.append((psku, pname, int(pqty)))
            idx += 1

        if not products:
            conn.close()
            return "제품명과 수량을 최소 1개 입력하세요.", 400

        # 거래처 이름 조회
        cursor.execute("SELECT name FROM suppliers WHERE id = %s", (supplier_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return "거래처를 찾을 수 없습니다.", 400
        supplier_name = row[0] if isinstance(row, tuple) else row["name"]

        # 기존 발주 삭제 후 재삽입
        cursor.execute("DELETE FROM orders WHERE order_code = %s", (order_code,))
        order_date = datetime.today().strftime("%Y-%m-%d")
        staff_name = user["name"]
        staff_english_name = user.get("english_name", "")

        for sku, name, qty in products:
            cursor.execute("""
                INSERT INTO orders (
                    order_code, supplier_id, supplier_name,
                    product_sku, product_name, quantity,
                    inquiry, order_date, staff_name, staff_english_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                order_code, supplier_id, supplier_name,
                sku, name, qty,
                inquiry, order_date, staff_name, staff_english_name  # 여기에 추가
            ))

        conn.commit()
        conn.close()
        return redirect(url_for("view_order", order_code=order_code))

    # GET 요청 처리
    cursor.execute("SELECT * FROM orders WHERE order_code = %s", (order_code,))
    items = cursor.fetchall()

    if not items:
        conn.close()
        return "발주서를 찾을 수 없습니다.", 404

    cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = cursor.fetchall()

    supplier_id = items[0]["supplier_id"]
    inquiry = items[0]["inquiry"]
    conn.close()

    return render_template(
        "edit_order.html",
        items=items,
        suppliers=suppliers,
        supplier_id=supplier_id,
        inquiry=inquiry,
        user=user,
        order_code=order_code
    )

def print_order(order_code):
    user = session.get("user")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("""
        SELECT 
            o.order_code,
            o.order_date,
            o.inquiry,
            o.quantity,
            o.product_sku,
            p.english_name,
            p.name AS product_name,
            s.name AS supplier_name
        FROM orders o
        JOIN products p ON o.product_sku = p.sku
        JOIN suppliers s ON o.supplier_id = s.id
        WHERE o.order_code = %s
    """, (order_code,))
    
    items = cursor.fetchall()
    conn.close()

    if not items:
        return "발주서를 찾을 수 없습니다.", 404

    return render_template("print_order.html", items=items, order_code=order_code, user=user)

def receive_order(order_code):
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        idx = 0
        while True:
            sku = request.form.get(f"sku_{idx}")
            name = request.form.get(f"name_{idx}")
            if not sku:
                break

            unit_per_box = safe_int(request.form.get(f"unit_per_box_{idx}", 1))
            box_qty = safe_int(request.form.get(f"box_qty_{idx}", 0))
            piece_qty = safe_int(request.form.get(f"piece_qty_{idx}", 0))
            warehouse = request.form.get(f"warehouse_{idx}")
            shelf_location = request.form.get(f"shelf_location_{idx}", "없음")

            # 유통기한 처리: 빈 값은 None으로
            expiration_date_str = request.form.get(f"expiration_date_{idx}", "").strip()
            expiration_date = expiration_date_str if expiration_date_str else None

            total_qty = box_qty * unit_per_box + piece_qty

            # 제품 정보 조회
            cursor.execute(
                "SELECT barcode, english_name FROM products WHERE sku = %s", (sku,)
            )
            product_row = cursor.fetchone() or {}
            barcode = product_row.get('barcode', '')
            english_name = product_row.get('english_name', '')

            # inventory 저장
            cursor.execute(
                """
                INSERT INTO inventory (
                    sku, product_name, english_name, barcode,
                    unit_per_box, box_qty, piece_qty, total_qty,
                    warehouse, shelf_location, order_number, expiration_date, is_expected
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                """, (
                    sku, name, english_name, barcode,
                    unit_per_box, box_qty, piece_qty, total_qty,
                    warehouse, shelf_location, order_code, expiration_date
                )
            )

            # 입출고 기록
            cursor.execute(
                """
                INSERT INTO inventory_movement (
                    sku, product_name, product_name_en, movement_type,
                    quantity_box, quantity_piece, to_warehouse, expiration_date
                ) VALUES (%s, %s, %s, '입고', %s, %s, %s, %s)
                """, (
                    sku, name, english_name,
                    box_qty, piece_qty, warehouse, expiration_date
                )
            )

            idx += 1

        conn.commit()
        conn.close()

        return redirect(
            url_for("receive_order", order_code=order_code, success="입고가 완료되었습니다.")
        )

    # GET 요청: 입고 완료된 SKU 확인
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT sku FROM inventory WHERE order_number = %s", (order_code,))
    received_skus = {row['sku'] for row in cursor.fetchall()}

    cursor.execute(
        """
        SELECT o.*, p.barcode
        FROM orders o
        LEFT JOIN products p ON o.product_sku = p.sku
        WHERE o.order_code = %s
        """, (order_code,)
    )
    all_items = cursor.fetchall()
    items = [item for item in all_items if item.get('product_sku') not in received_skus]

    conn.close()

    success = request.args.get("success")
    error = request.args.get("error")

    if not items:
        return render_template(
            "receive_order.html",
            items=[],
            order_code=order_code,
            success="모든 품목이 입고되었습니다."
        )

    return render_template(
        "receive_order.html",
        items=items,
        order_code=order_code,
        success=success,
        error=error
    )


def delete_order(order_code):
    user = session.get("user")
    if not user:
        return "로그인 정보가 없습니다.", 403

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT staff_name FROM orders WHERE order_code = %s", (order_code,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return "해당 발주서를 찾을 수 없습니다.", 404

    staff_name = row[0]  # 또는 row["staff_name"] if RealDictCursor 사용 시

    if user["name"] != staff_name:
        conn.close()
        return "해당 발주서를 삭제할 권한이 없습니다.", 403

    cursor.execute("DELETE FROM orders WHERE order_code = %s", (order_code,))
    conn.commit()
    conn.close()

    return redirect(url_for("list_orders"))



def generate_order_code():
    year = datetime.today().strftime("%y")  # 예: '25'
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        "SELECT COUNT(DISTINCT order_code) AS cnt FROM orders WHERE order_code LIKE %s",
        (f"{year}-%",)
    )

    row = cursor.fetchone()
    count = row["cnt"]  # 인덱스 대신 키 접근
    conn.close()
    # 네 자리 시퀀스: 0001, 0002, ...
    return f"{year}-{count + 1:04d}"
    
def create_order_table():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            order_code TEXT NOT NULL,
            supplier_id INTEGER NOT NULL,
            supplier_name TEXT NOT NULL,
            product_sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            inquiry TEXT,
            order_date TEXT NOT NULL,
            staff_name TEXT NOT NULL,
            staff_english_name TEXT  -- 여기 추가된 컬럼입니다!
        )
    """)
    conn.commit()
    conn.close()
