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
                reader = csv.DictReader(stream)

                cursor.execute("""
                    DELETE FROM sales_volume
                    WHERE year = %s AND month = %s
                """, (year_int, month_int))

                inserted = 0
                skipped = 0

                for row in reader:
                    sku = row.get("SKU", "").strip()
                    qty = row.get("판매수량", "").strip()

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
                        INSERT INTO sales_volume (sku, year, month, quantity)
                        VALUES (%s, %s, %s, %s)
                    """, (sku, year_int, month_int, qty_int))
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

    # 실재고 데이터
    cursor.execute("""
        SELECT
            sku,
            MIN(product_name) AS product_name,   -- MIN()으로 대표값 집계
            expiry_text,
            SUM(quantity)     AS quantity
        FROM real_stock
        GROUP BY
            sku,
            expiry_text
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
    recent_months = []
    today = date.today()
    for i in range(12):
        dt = today - relativedelta(months=i)
        recent_months.append(dt.strftime("%Y-%m"))

    # 판매량 데이터
    cursor.execute("SELECT sku, year, month, quantity FROM sales_volume")
    sales_data = cursor.fetchall()

    sales_by_sku = defaultdict(lambda: defaultdict(int))
    for row in sales_data:
        ym = f"{row['year']:04d}-{row['month']:02d}"
        if ym in recent_months:
            sales_by_sku[row["sku"]][ym] += row["quantity"]

    # 평균판매량 (최근 4개월)
    recent_4 = recent_months[:4]
    avg_sales = {}
    for sku, month_dict in sales_by_sku.items():
        values = [month_dict.get(m, 0) for m in recent_4]
        avg_sales[sku] = round(sum(values) / 4, 2) if values else 0

    # 입고예정 계산
    cursor.execute("SELECT order_code, product_sku, product_name, quantity FROM orders")
    all_orders = cursor.fetchall()

    cursor.execute("SELECT sku, order_number FROM inventory")
    received = set((r["sku"], r["order_number"]) for r in cursor.fetchall())

    incoming = defaultdict(int)
    for row in all_orders:
        key = (row["product_sku"], row["order_code"])
        if key not in received:
            incoming[row["product_sku"]] += row["quantity"]

    conn.close()

    # 결과 병합
    final_data = []
    for (sku, expiry), stock in stock_dict.items():
        row = dict(stock)
        row["incoming_qty"] = incoming.get(sku, 0)
        row["avg_sales"] = avg_sales.get(sku, 0)

        for month in recent_months:
            row[month] = sales_by_sku.get(sku, {}).get(month, 0)

        final_data.append(row)

    # 검색 필터
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
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
