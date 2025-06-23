# run_migration.py

import sqlite3

def rename_orders_to_backup():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE orders RENAME TO orders_backup;")
    conn.commit()
    conn.close()
    print("[1/3] orders → orders_backup 테이블 이름 변경 완료")

def create_new_orders_table():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT NOT NULL,
            supplier_id INTEGER NOT NULL,
            supplier_name TEXT NOT NULL,
            product_sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            inquiry TEXT,
            order_date TEXT NOT NULL,
            staff_name TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    print("[2/3] 새 orders 테이블 생성 완료 (UNIQUE 제거됨)")

def copy_data_to_new_orders():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (
            order_code, supplier_id, supplier_name,
            product_sku, product_name, quantity,
            inquiry, order_date, staff_name
        )
        SELECT
            order_code, supplier_id, supplier_name,
            product_sku, product_name, quantity,
            inquiry, order_date, staff_name
        FROM orders_backup;
    """)
    conn.commit()
    conn.close()
    print("[3/3] 백업 데이터 새 테이블로 복사 완료")

if __name__ == "__main__":
    rename_orders_to_backup()
    create_new_orders_table()
    copy_data_to_new_orders()
    print("✅ 마이그레이션 성공적으로 완료되었습니다.")
