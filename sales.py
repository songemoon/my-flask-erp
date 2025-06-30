from flask import request, render_template, redirect, url_for, flash, get_flashed_messages
from datetime import date
from collections import defaultdict
import io
import csv
from dateutil.relativedelta import relativedelta
import psycopg2
import psycopg2.extras
from db import get_db_connection  # PostgreSQL 연결 함수

def upload_sales_volume():
    message = None

    if request.method == "POST":
        file = request.files.get("file")
        year = request.form.get("year", "").strip()
        month = request.form.get("month", "").strip()

        if not file or not year or not month:
            message = "❌ 연도, 월, 파일을 모두 입력해주세요."
        else:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                year_int = int(year)
                month_int = int(month)

                stream = io.StringIO(file.stream.read().decode("utf-8"))
                reader = csv.DictReader(stream, delimiter=';')
                reader.fieldnames = [f.strip().replace('\ufeff', '') for f in reader.fieldnames]

                cursor.execute("""
                    DELETE FROM sales_volume
                    WHERE year = %s AND month = %s
                """, (year_int, month_int))

                inserted = 0
                skipped = 0

                for row in reader:
                    sku = row.get("SKU", "").strip()
                    name = row.get("제품명", "").strip()
                    qty = row.get("판매량", "").strip()

                    if not sku or not qty:
                        print("⚠️ 필수 항목 누락:", row)
                        skipped += 1
                        continue

                    try:
                        qty_int = int(qty)
                    except ValueError:
                        print("❌ 숫자 변환 실패:", row)
                        skipped += 1
                        continue

                    cursor.execute("""
                        INSERT INTO sales_volume (sku, product_name, year, month, quantity)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (sku, name, year_int, month_int, qty_int))
                    inserted += 1

                conn.commit()
                message = f"✅ 판매량 업로드 완료: {inserted}건 삽입, {skipped}건 건너뜀"

            except Exception as e:
                conn.rollback()
                message = f"❌ 업로드 중 오류 발생: {e}"

            finally:
                conn.close()

    return render_template("upload_sales.html", message=message)

def sales_overview():
    query = request.args.get("q", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # 제품 정보
    cursor.execute("SELECT sku, name, barcode FROM products")
    product_info = {
        row["sku"]: {"product_name": row["name"], "barcode": row["barcode"]}
        for row in cursor.fetchall()
    }

    # 우커머스 재고 (= real_stock)
    cursor.execute("""
        SELECT
            sku,
            MIN(product_name) AS product_name,
            expiry_text,
            SUM(quantity) AS quantity
        FROM real_stock
        GROUP BY sku, expiry_text
    """)
    stock_data = cursor.fetchall()
    stock_dict = {}
    for row in stock_data:
        key = (row["sku"], row["expiry_text"])
        stock_dict[key] = {
            "sku": row["sku"],
            "product_name": row["product_name"],
            "expiry_text": row["expiry_text"],
            "real_stock": row["quantity"]
        }

    # 최근 12개월
    recent_months = [(date.today() - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]

    # 판매량
    cursor.execute("SELECT sku, year, month, quantity FROM sales_volume")
    sales_data = cursor.fetchall()
    sales_by_sku = defaultdict(lambda: defaultdict(int))
    for row in sales_data:
        ym = f"{row['year']:04d}-{row['month']:02d}"
        if ym in recent_months:
            sales_by_sku[row["sku"]][ym] += row["quantity"]

    # 평균 판매량 (최근 4개월)
    recent_4 = recent_months[:4]
    avg_sales = {
        sku: round(sum(month_dict.get(m, 0) for m in recent_4) / 4, 2)
        for sku, month_dict in sales_by_sku.items()
    }

    # 입고예정
    cursor.execute("SELECT order_code, product_sku, quantity FROM orders")
    all_orders = cursor.fetchall()
    cursor.execute("SELECT sku, order_number FROM inventory")
    received = set((r["sku"], r["order_number"]) for r in cursor.fetchall())
    incoming = defaultdict(int)
    for row in all_orders:
        if (row["product_sku"], row["order_code"]) not in received:
            incoming[row["product_sku"]] += row["quantity"]

    # 창고 기준 재고 계산
    cursor.execute("""
        SELECT sku, warehouse, SUM(total_qty) AS qty
        FROM inventory
        WHERE is_active = 1
        GROUP BY sku, warehouse
    """)
    wh_data = cursor.fetchall()
    total_stock = defaultdict(int)
    available_stock = defaultdict(int)
    for row in wh_data:
        sku = row["sku"]
        warehouse = row["warehouse"]
        qty = row["qty"]
        if warehouse in ("신창고 A", "매장창고 B"):
            total_stock[sku] += qty
        elif warehouse == "가용재고 S":
            available_stock[sku] += qty

    conn.close()

    # 최종 병합
    final_data = []
    for (sku, expiry), stock in stock_dict.items():
        row = dict(stock)
        product = product_info.get(sku, {})
        row["product_name"] = product.get("product_name", row["product_name"])
        row["barcode"] = product.get("barcode", "")
        row["incoming_qty"] = incoming.get(sku, 0)
        row["avg_sales"] = avg_sales.get(sku, 0)
        row["total_stock"] = total_stock.get(sku, 0)
        row["available_stock"] = available_stock.get(sku, 0)
        row["stock_ratio"] = round((row["total_stock"] + row["available_stock"]) / row["avg_sales"], 2) if row["avg_sales"] else 0
        for month in recent_months:
            row[month] = sales_by_sku.get(sku, {}).get(month, 0)
        final_data.append(row)

    if query:
        final_data = [
            r for r in final_data
            if query.lower() in r["sku"].lower() or query.lower() in r.get("product_name", "").lower()
        ]

    return render_template("sales_overview.html", results=final_data, months=recent_months, query=query)


def create_sales_volume_table():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales_volume (
            id SERIAL PRIMARY KEY,
            sku TEXT NOT NULL,
            product_name TEXT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_product_name_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE sales_volume ADD COLUMN product_name TEXT;")
        conn.commit()
        print("✅ product_name 컬럼 추가 완료")
    except Exception as e:
        print("❌ 에러 발생:", e)
        conn.rollback()
    finally:
        conn.close()

# 아래 한 줄을 실행 시점에만 잠깐 추가
#add_product_name_column()

