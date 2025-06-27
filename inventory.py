from flask import request, render_template, redirect, url_for, Blueprint
from datetime import datetime, timedelta, date
from collections import defaultdict
import psycopg2
import psycopg2.extras
from db import get_db_connection




def create_inventory_table():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            english_name TEXT NOT NULL,
            barcode TEXT,
            unit_per_box INTEGER NOT NULL,
            box_qty INTEGER NOT NULL,
            piece_qty INTEGER NOT NULL,
            total_qty INTEGER NOT NULL,
            warehouse TEXT NOT NULL,
            shelf_location TEXT,
            order_number TEXT,
            expiration_date DATE,
            is_expected INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def inventory_in():
    if request.method == "POST":
        identifier = request.form.get("identifier")
        if not identifier:
            return render_template("manage_inventory.html", action="in", message="❌ 제품 식별자가 입력되지 않았습니다.", identifier="", product=None)

        identifier = identifier.strip()

        # 안전한 숫자 변환 처리
        box_qty = safe_int(request.form.get("box_qty", 0))
        piece_qty = safe_int(request.form.get("piece_qty", 0))
        unit_per_box = safe_int(request.form.get("unit_per_box", 1))

        warehouse = request.form.get("warehouse")
        shelf_location = request.form.get("shelf_location")
        order_number = request.form.get("order_number")
        expiration_date_str = request.form.get("expiration_date", "").strip()
        if expiration_date_str == "":
            expiration_date = None
        else:
            expiration_date = expiration_date_str
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT sku, name, english_name, barcode FROM products WHERE sku = %s OR barcode = %s", (identifier, identifier))
        products = cursor.fetchall()

        if not products:
            conn.close()
            return render_template(
                "manage_inventory.html",
                action="in",
                message="❌ 해당 SKU 또는 바코드의 제품을 찾을 수 없습니다.",
                identifier=identifier,
                product=None
            )

        if len(products) == 1 or any(p["sku"] == identifier for p in products):
            product = next((p for p in products if p["sku"] == identifier), products[0])
            sku          = product["sku"]
            name         = product["name"]
            english_name = product["english_name"]
            barcode      = product["barcode"]
        else:
            conn.close()
            return render_template(
                "select_product.html",
                action="in",
                identifier=identifier,
                products=products
            )

        sku = product["sku"]
        name = product["name"]
        english_name = product["english_name"]
        barcode = product["barcode"]
        total_qty = box_qty * unit_per_box + piece_qty

        cursor.execute("""
            INSERT INTO inventory (
                sku, product_name, english_name, barcode,
                unit_per_box, box_qty, piece_qty, total_qty,
                warehouse, shelf_location, order_number, expiration_date, is_expected
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
        """, (
            sku, name, english_name, barcode,
            unit_per_box, box_qty, piece_qty, total_qty,
            warehouse, shelf_location, order_number, expiration_date
        ))

        cursor.execute("""
            INSERT INTO inventory_movement (
                sku, product_name, product_name_en, movement_type,
                quantity_box, quantity_piece, to_warehouse, expiration_date
            ) VALUES (%s, %s, %s, '입고', %s, %s, %s, %s)
        """, (
            sku, name, english_name, box_qty, piece_qty, warehouse, expiration_date
        ))

        conn.commit()
        conn.close()

        return render_template(
            "manage_inventory.html",
            action="in",
            message=f"✅ 제품 {name} 입고 완료. 총 수량: {total_qty}개",
            identifier=identifier,
            product={"sku": sku, "name": name, "english_name": english_name}
        )

    return render_template("manage_inventory.html", action="in")


def inventory_out():
    message = None
    warning = ""
    name = ""
    english_name = ""
    identifier = None

    if request.method == "POST":
        identifier = request.form.get("identifier")
        if not identifier:
            message = "❌ 제품 식별자가 입력되지 않았습니다."
            return render_template("manage_inventory.html", action="out", message=message, identifier="", product=None)

        identifier = identifier.strip()
        movement_type = request.form.get("movement_type")
        warehouse = request.form.get("warehouse")
        box_qty = safe_int(request.form.get("box_qty", 0))
        piece_qty = safe_int(request.form.get("piece_qty", 0))
        unit_per_box = safe_int(request.form.get("unit_per_box", 1))
        expiration_date = request.form.get("expiration_date")
        reason = request.form.get("reason")

        total_out_qty = box_qty * unit_per_box + piece_qty
        today = datetime.today().date()

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 제품 조회
        cursor.execute(
            "SELECT sku, name, english_name, barcode FROM products WHERE sku = %s OR barcode = %s",
            (identifier, identifier)
        )
        products = cursor.fetchall()
        if not products:
            conn.close()
            message = "❌ 해당 SKU 또는 바코드의 제품을 찾을 수 없습니다."
            return render_template("manage_inventory.html", action="out", message=message, identifier=identifier, product=None)

        # 단일 제품 선택
        if len(products) == 1 or any(p["sku"] == identifier for p in products):
            product = next((p for p in products if p["sku"] == identifier), products[0])
            sku = product["sku"]
        else:
            conn.close()
            return render_template(
                "select_product.html",
                action="out",
                identifier=identifier,
                products=products,
                preserved=request.form
            )

        # 유통기한 미지정 시 재고 조회
        if not expiration_date or expiration_date.strip() == "":
            cursor.execute(
                "SELECT id, expiration_date, total_qty FROM inventory "
                "WHERE sku = %s AND total_qty > 0 "
                "ORDER BY expiration_date ASC LIMIT 1",
                (sku,)
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                message = "❌ 출고 가능한 재고가 없습니다."
                return render_template("manage_inventory.html", action="out", message=message, identifier=identifier, product=None)

            # 수정된 부분: dict key 접근 및 None 처리
            inventory_id = row["id"]
            exp_date = row["expiration_date"]
            current_qty = row["total_qty"]

            if exp_date is None:
                expiration_date = None
            elif isinstance(exp_date, str):
                expiration_date = exp_date
            else:
                expiration_date = exp_date.strftime("%Y-%m-%d")
            # ✅ 유통기한 경고 메시지 구성
        try:
            if expiration_date:
                if isinstance(expiration_date, str):
                    exp_date_obj = datetime.strptime(expiration_date, "%Y-%m-%d").date()
                else:
                    exp_date_obj = expiration_date

                today = datetime.today().date()
                days_left = (exp_date_obj - today).days

                if days_left < 0:
                    warning = f"⚠️ 유통기한이 경과된 상품입니다: {expiration_date}"
                elif days_left <= 30:
                    warning = f"⚠️ 유통기한이 30일 이하입니다 ({days_left}일 남음): {expiration_date}"
        except Exception as e:
            warning = "⚠️ 유통기한 확인 중 오류 발생"

        else:
            cursor.execute(
                "SELECT id, total_qty FROM inventory "
                "WHERE sku = %s AND expiration_date = %s AND total_qty > 0 LIMIT 1",
                (sku, expiration_date)
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                message = f"❌ 해당 유통기한({expiration_date}) 재고 없음."
                return render_template("manage_inventory.html", action="out", message=message, identifier=identifier, product=None)

            inventory_id = row["id"]
            current_qty = row["total_qty"]

        # 재고 부족 체크
        if total_out_qty > current_qty:
            conn.close()
            message = f"❌ 재고 부족: 현재 {current_qty}개, 요청 {total_out_qty}개"
            return render_template("manage_inventory.html", action="out", message=message, identifier=identifier, product=None)

        # 출고 후 재고 업데이트
        cursor.execute("UPDATE inventory SET total_qty = total_qty - %s WHERE id = %s", (total_out_qty, inventory_id))

        # 제품명 조회 및 dict 접근
        cursor.execute("SELECT name, english_name FROM products WHERE sku = %s", (sku,))
        row = cursor.fetchone()
        if row:
            name = row["name"]
            english_name = row["english_name"]
        else:
            name = "알수없음"
            english_name = "unknown"

        # 이동 기록
        cursor.execute(
            """
            INSERT INTO inventory_movement (
                sku, product_name, product_name_en, movement_type,
                quantity_box, quantity_piece,
                from_warehouse, expiration_date, reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (sku, name, english_name, movement_type, box_qty, piece_qty, warehouse, expiration_date, reason)
        )

        conn.commit()
        conn.close()

        message = f"{movement_type} 완료. 총 {total_out_qty}개 차감됨."
        if warning:
            message = f"{warning}<br>{message}"

        return render_template(
            "manage_inventory.html",
            action="out",
            message=message,
            identifier=identifier,
            product={"name": name, "english_name": english_name}
        )

    return render_template("manage_inventory.html", action="out", identifier="", message=message, product=None)


def search_inventory():
    query = request.args.get("q", "").strip()
    today = datetime.today().date()

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 전체 재고 처리
    cursor.execute("UPDATE inventory SET is_active = 0 WHERE total_qty = 0")
    conn.commit()

    cursor.execute("SELECT * FROM inventory WHERE is_active = 1")
    all_rows = cursor.fetchall()


    def highlight_row(row_dict):
        exp = row_dict.get("expiration_date")
        if not exp:
            return ""
        # exp가 date 객체라면 그대로, 문자열이라면 파싱
        if isinstance(exp, str):
            try:
                exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except ValueError:
                return ""
        else:
            exp_date = exp
        if exp_date < today:
            return "expired"
        elif (exp_date - today).days <= 30:
            return "expiring"
        return ""

    all_inventory = []
    for row_dict in all_rows:
        row_dict["highlight"] = highlight_row(row_dict)
        all_inventory.append(row_dict)

    grouped_inventory = defaultdict(list)
    for item in all_inventory:
        grouped_inventory[item["warehouse"]].append(item)

    # 검색 결과 필터링
    results = []
    if query:
        for r in all_inventory:
            if query.lower() in (r["product_name"] or "").lower() \
            or query.lower() in (r["sku"] or "").lower() \
            or query.lower() in (r["barcode"] or "").lower():
                results.append(r)

    # 🔹 입고예정 항목 처리
    cursor.execute("SELECT order_code, product_sku, product_name FROM orders")
    all_orders = cursor.fetchall()

    cursor.execute("SELECT sku, order_number FROM inventory")
    received_rows = cursor.fetchall()

    received_set = set((row["sku"], row["order_number"]) for row in received_rows)

    pending_items = []
    for row in all_orders:  # ✅ row는 이미 dict
        key = (row["product_sku"], row["order_code"])
        if key not in received_set:
            pending_items.append(row)  # ✅ 그대로 사용

    conn.close()

    return render_template(
        "search_inventory.html",
        results=results,
        query=query,
        all_inventory=all_inventory,
        grouped_inventory=grouped_inventory,
        pending_items=pending_items
    )

def warehouse_transfer():
    message = None
    identifier = None
    name = ""
    english_name = ""
    product_data = None

    if request.method == "POST":
        identifier = request.form.get("identifier")
        if not identifier:
            message = "❌ 제품 식별자가 입력되지 않았습니다."
            return render_template("manage_inventory.html", action="transfer", message=message, identifier=identifier, product=None)

        identifier = identifier.strip()
        unit_per_box = safe_int(request.form.get("unit_per_box", 1))
        box_qty = safe_int(request.form.get("box_qty", 0))
        piece_qty = safe_int(request.form.get("piece_qty", 0))
        from_warehouse = request.form.get("from_warehouse")
        to_warehouse = request.form.get("to_warehouse")
        expiration_date = request.form.get("expiration_date")
        total_qty = box_qty * unit_per_box + piece_qty

        if from_warehouse == to_warehouse:
            message = "❌ 출발창고와 도착창고가 동일합니다."
            return render_template("manage_inventory.html", action="transfer", message=message, identifier=identifier, product=None)

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT sku, name, english_name, barcode FROM products WHERE sku = %s OR barcode = %s", (identifier, identifier))
        products = cursor.fetchall()

        if not products:
            conn.close()
            message = "❌ 해당 SKU 또는 바코드의 제품을 찾을 수 없습니다."
            return render_template("manage_inventory.html", action="transfer", message=message, identifier=identifier, product=None)

        if len(products) == 1 or any(p["sku"] == identifier for p in products):
            product = next((p for p in products if p["sku"] == identifier), products[0])
            sku          = product["sku"]
            name         = product["name"]
            english_name = product["english_name"]
            barcode      = product["barcode"]
        else:
            conn.close()
            return render_template(
                "select_product.html",
                action="transfer",
                identifier=identifier,
                products=products,
                preserved=request.form
            )

        if not expiration_date:
            cursor.execute("""
                SELECT id, expiration_date, total_qty FROM inventory
                WHERE sku = %s AND warehouse = %s AND total_qty > 0
                ORDER BY expiration_date ASC
                LIMIT 1
            """, (sku, from_warehouse))
            row = cursor.fetchone()

            if not row:
                conn.close()
                message = "❌ 이동 가능한 재고가 없습니다."
                return render_template("manage_inventory.html", action="transfer", message=message, identifier=identifier, product=product_data)

            inventory_id = row["id"]
            expiration_date = row["expiration_date"]
            current_qty = int(row["total_qty"] or 0)
        else:
            cursor.execute("""
                SELECT id, total_qty FROM inventory
                WHERE sku = %s AND warehouse = %s AND expiration_date = %s
            """, (sku, from_warehouse, expiration_date))
            row = cursor.fetchone()

            if not row:
                conn.close()
                message = f"❌ {from_warehouse}의 해당 유통기한 재고 없음"
                return render_template("manage_inventory.html", action="transfer", message=message, identifier=identifier, product=product_data)

            inventory_id = row["id"]
            current_qty = int(row["total_qty"] or 0)

        if total_qty > current_qty:
            conn.close()
            message = f"❌ 재고 부족: 보유 {current_qty}개, 요청 {total_qty}개"
            return render_template("manage_inventory.html", action="transfer", message=message, identifier=identifier, product=product_data)

        cursor.execute("UPDATE inventory SET total_qty = total_qty - %s WHERE id = %s", (total_qty, inventory_id))

        cursor.execute("""
            SELECT id, total_qty FROM inventory
            WHERE sku = %s AND warehouse = %s AND expiration_date = %s
        """, (sku, to_warehouse, expiration_date))
        existing = cursor.fetchone()

        if existing:
            dest_id, dest_qty = existing
            cursor.execute("UPDATE inventory SET total_qty = total_qty + %s WHERE id = %s", (total_qty, dest_id))
        else:
            cursor.execute("""
                INSERT INTO inventory (
                    sku, product_name, english_name, barcode,
                    unit_per_box, box_qty, piece_qty, total_qty,
                    warehouse, expiration_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                sku, name, english_name, barcode,
                unit_per_box, box_qty, piece_qty, total_qty,
                to_warehouse, expiration_date
            ))

        cursor.execute("""
            INSERT INTO inventory_movement (
                sku, product_name, product_name_en, movement_type,
                quantity_box, quantity_piece,
                from_warehouse, to_warehouse, expiration_date
            ) VALUES (%s, %s, %s, '창고이동', %s, %s, %s, %s, %s)
        """, (
            sku, name, english_name, box_qty, piece_qty, from_warehouse, to_warehouse, expiration_date
        ))

        conn.commit()
        conn.close()

        message = f"✅ 창고 이동 완료: {from_warehouse} → {to_warehouse}, {total_qty}개"

    return render_template(
        "manage_inventory.html",
        action="transfer",
        message=message,
        identifier=identifier,
        product=product_data
    )

def manage_inventory():
    action = request.args.get("action", "in")
    identifier = None
    product = None

    if request.method == "POST":
        action = request.form.get("action")
        identifier = request.form.get("identifier", "").strip()

        # 1단계: 제품 식별자만 입력된 경우 → 제품정보 조회
        if "box_qty" not in request.form:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT sku, name, english_name FROM products WHERE sku = %s OR barcode = %s", (identifier, identifier))
            row = cursor.fetchone()
            conn.close()

            if row:
                product = {
                    "sku":          row["sku"],
                    "name":         row["name"],
                    "english_name": row["english_name"],
                }
            else:
                return render_template(
                    "manage_inventory.html",
                    action=action,
                    message=f"❌ 제품을 찾을 수 없습니다: {identifier}",
                    identifier=identifier,
                    product=None
                )

        # 2단계: 실제 등록 처리
        else:
            if action == "in":
                return inventory_in()
            elif action == "out":
                return inventory_out()
            elif action == "transfer":
                return warehouse_transfer()
            else:
                return "❌ 잘못된 작업 요청입니다."

    return render_template("manage_inventory.html", action=action, product=product, identifier=identifier)
