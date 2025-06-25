import psycopg2
import psycopg2.extras
from flask import request, render_template, redirect, url_for
import io
import csv
from db import get_db_connection  # PostgreSQL 접속 함수

def create_real_stock_table():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS real_stock (
            id SERIAL PRIMARY KEY,
            sku TEXT NOT NULL,
            product_name TEXT,
            quantity INTEGER NOT NULL,
            expiry_text TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def upload_real_stock():
    message = None
    conn = None  # ✅ 사전 선언

    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            message = "❌ 파일이 없습니다."
        else:
            try:
                stream = io.StringIO(file.stream.read().decode("utf-8"))
                reader = csv.DictReader(stream, delimiter=';')

                conn = get_db_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                # 기존 데이터 삭제
                cursor.execute("DELETE FROM real_stock")

                for row in reader:
                    sku = row.get("SKU", "").strip()
                    name = row.get("제품명", "").strip()
                    qty = row.get("재고", "").strip()
                    expiry = row.get("유통기한", "").strip() or "미정"

                    if not sku or not qty:
                        continue

                    try:
                        qty_int = int(qty)
                    except ValueError:
                        continue

                    cursor.execute("""
                        INSERT INTO real_stock (sku, product_name, quantity, expiry_text)
                        VALUES (%s, %s, %s, %s)
                    """, (sku, name, qty_int, expiry))

                conn.commit()
                message = "✅ 실재고 업로드 완료 (기존 데이터 초기화됨)"

            except Exception as e:
                if conn:  # ✅ conn이 존재할 때만 rollback
                    conn.rollback()
                message = f"❌ 업로드 중 오류 발생: {e}"

            finally:
                if conn:  # ✅ conn이 존재할 때만 close
                    conn.close()

    return render_template("upload_stock.html", message=message)
