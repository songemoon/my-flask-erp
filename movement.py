import sqlite3
from flask import request, render_template
from datetime import datetime, timedelta, date

def view_movements():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    search_keyword = request.args.get("search_keyword")
    movement_type = request.args.get("movement_type")
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT m.*, p.name AS product_name, p.english_name AS product_name_en, p.barcode
        FROM inventory_movement m
        LEFT JOIN products p ON m.sku = p.sku
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND DATE(m.timestamp) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND DATE(m.timestamp) <= ?"
        params.append(end_date)
    if movement_type:
        query += " AND m.movement_type = ?"
        params.append(movement_type)
    if search_keyword:
        keyword = f"%{search_keyword}%"
        query += """
            AND (
                m.sku LIKE ?
                OR p.barcode LIKE ?
                OR p.name LIKE ?
                OR p.english_name LIKE ?
            )
        """
        params.extend([keyword, keyword, keyword, keyword])

    query += " ORDER BY m.timestamp DESC"

    cursor.execute(query, params)
    movements = cursor.fetchall()
    conn.close()

    return render_template("inventory_movements.html", movements=movements)

def create_inventory_movement_table():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_movement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            product_name TEXT,
            product_name_en TEXT,
            movement_type TEXT NOT NULL,
            quantity_box INTEGER,
            quantity_piece INTEGER,
            from_warehouse TEXT,
            to_warehouse TEXT,
            expiration_date TEXT,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()