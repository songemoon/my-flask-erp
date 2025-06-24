import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import os
import psycopg2
import psycopg2.extras
from db import get_db_connection
from common import COUNTRY_CODE_MAP
from config import Config
from product import (
    create_table,
    generate_sku,
    register_product as product_register_product,
    view_products as product_view_products,
    edit_product as product_edit_product,
    delete_product as product_delete_product,
    product_info,
    product_search as product_product_search,
    manage_products as product_manage_products,
)
from inventory import (
    create_inventory_table,
    inventory_in as inventory_inventory_in,
    inventory_out as inventory_inventory_out,
    search_inventory as inventory_search_inventory,
    warehouse_transfer as inventory_warehouse_transfer,
    manage_inventory as inventory_manage_inventory,
)
from movement import view_movements, create_inventory_movement_table
from order import (
    create_order_table,
    generate_order_code,
    new_order as order_new_order,
    edit_order as order_edit_order,
    view_order as order_view_order,
    list_orders as order_list_orders,
    print_order as order_print_order,
    receive_order as order_receive_order,
    delete_order as order_delete_order,
)
from cost import (
    initialize_cost_expense_table,
    create_cost_history_table,
    create_cost_expense_table,
    register_cost as cost_register_cost,
    view_cost_history as cost_view_cost_history,
)
from sales import (
    create_sales_volume_table,
    upload_sales_volume as sales_upload_sales_volume,
    sales_overview as sales_sales_overview,
)
from supplier import (
    create_supplier_table,
    generate_supplier_code,
    manage_suppliers as supplier_manage_suppliers,
    delete_supplier as supplier_delete_supplier,
)
from stock import (
    create_real_stock_table,
    upload_real_stock as stock_upload_real_stock,
)
from auth import (
    create_user_table,
    authenticate_user,
    hash_password,
    admin_add_user as auth_admin_add_user,
    login as auth_login,
    login_required,
    admin_delete_user as auth_admin_delete_user,
    admin_user_list as auth_admin_user_list,
    admin_user_manage,
    change_password
)
from schedule_routes import (create_schedule_table)
from order import reset_order_table, create_order_table

app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']



@app.route("/reset-orders")
def reset_orders():
    reset_order_table()   # 기존 orders 테이블 삭제
    create_order_table()  # 새로 orders 테이블 생성
    return "✅ orders 테이블이 초기화되었습니다."


@app.route("/")
def home():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    return render_template("home.html")

@app.route("/admin/add_user", methods=["GET", "POST"])
def admin_add_user():
    return auth_admin_add_user()

@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required  # 관리자 권한 검사 추가 권장
def delete_user_route(user_id):
    # 관리자 권한 체크 로직 별도 구현 권장
    return auth_admin_delete_user(user_id)

@app.route("/login", methods=["GET", "POST"])
def login():
    return auth_login()

@app.route("/profile/change-password", methods=["GET", "POST"])
@login_required
def change_password_route():
    return change_password()

@app.route("/logout")
def logout_route():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route("/admin/users", methods=["GET", "POST"])
def admin_user_manage_route():
    # 로그인/관리자 권한 체크는 별도 처리 권장
    return admin_user_manage()

@app.route("/protected")
def protected():
    user = session.get("user")
    if not user:
        return redirect(url_for("login", next=request.path))

@app.route("/register", methods=["GET", "POST"])
@login_required
def register_product():
    return product_register_product()

@app.route("/products")
@login_required
def view_products():
    return product_view_products()

@app.route('/products/upload', methods=['GET', 'POST'])
@login_required
def upload_products():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file:
            flash('CSV 파일을 선택해주세요.')
            return redirect(request.url)
        try:
            import io, csv
            stream = io.StringIO(file.stream.read().decode('utf-8'))
            reader = csv.DictReader(stream)

            for row in reader:
                name = row.get('제품명')
                english_name = row.get('영문명')
                category_main = row.get('대분류')
                category_sub = row.get('소분류')
                barcode = row.get('바코드', '').strip()

                if not (name and english_name and category_main and category_sub):
                    continue  # 필수값 없으면 건너뜀

                # 접미코드는 빈값으로 고정 (필요 시 CSV에 추가 가능)
                category_suffix = ''

                # SKU 생성 (product.py의 generate_sku 사용)
                try:
                    sku = generate_sku(category_main, category_sub, category_suffix)
                except Exception as e:
                    # 유효하지 않은 카테고리 등 에러 처리
                    continue

                # DB 저장
                conn = get_db_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    INSERT INTO products 
                    (sku, name, english_name, category_main, category_sub, category_suffix, barcode)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (sku, name, english_name, category_main, category_sub, category_suffix, barcode))
                conn.commit()
                conn.close()

            flash('CSV 대량 등록이 완료되었습니다.')
            return redirect(url_for('manage_products'))

        except Exception as e:
            flash(f'업로드 중 오류가 발생했습니다: {str(e)}')
            return redirect(request.url)

    return render_template('upload_products.html')

@app.route("/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    return product_edit_product(product_id)

@app.route("/delete/<int:product_id>")
@login_required
def delete_product(product_id):
    return product_delete_product(product_id)

@app.route("/products/manage", methods=["GET", "POST"])
@login_required
def manage_products():
    return product_manage_products()

@app.route("/api/get_products_by_barcode", methods=["GET"])
def get_products_by_barcode():
    identifier = request.args.get("identifier", "").strip()

    if not identifier:
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # SKU 또는 바코드가 일치하는 제품 모두 조회
    cursor.execute("""
        SELECT sku, name, english_name 
        FROM products 
        WHERE sku = %s OR barcode = %s
    """, (identifier, identifier))
    
    products = cursor.fetchall()
    conn.close()

    # 결과를 JSON 형태로 반환
    return jsonify([dict(p) for p in products])


@app.route("/inventory/manage", methods=["GET", "POST"])
@login_required
def manage_inventory():
    return inventory_manage_inventory()

@app.route("/inventory/in", methods=["GET", "POST"])
@login_required
def inventory_in():
    return inventory_inventory_in()

@app.route("/inventory/out", methods=["GET", "POST"])
@login_required
def inventory_out():
    return inventory_inventory_out()

@app.route("/inventory/transfer", methods=["GET", "POST"])
@login_required
def warehouse_transfer():
    return inventory_warehouse_transfer()

@app.route("/inventory/search", methods=["GET"])
@login_required
def search_inventory():
    return inventory_search_inventory()

@app.route("/inventory/movements", methods=["GET"])
@login_required
def view_movements_view():
    return view_movements()

@app.route("/suppliers/manage", methods=["GET", "POST"])
@login_required
def manage_suppliers():
    return supplier_manage_suppliers()


@app.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
@login_required
def delete_supplier(supplier_id):
    return supplier_delete_supplier(supplier_id)

@app.route("/api/product_search")
@login_required
def product_search():
    return product_product_search()

@app.route("/orders/new", methods=["GET", "POST"])
@login_required
def new_order():
    return order_new_order()

@app.route("/orders/edit/<path:order_code>", methods=["GET", "POST"])
@login_required
def edit_order(order_code):
    return order_edit_order(order_code)

@app.route("/orders/<order_code>")
@login_required
def view_order(order_code):
    return order_view_order(order_code)

@app.route("/orders", methods=["GET"])
@login_required
def list_orders():
    return order_list_orders()

@app.route("/orders/print/<order_code>")
@login_required
def print_order(order_code):
    return order_print_order(order_code)

@app.route("/orders/delete/<order_code>", methods=["POST"])
@login_required
def delete_order_route(order_code):
    return order_delete_order(order_code)

@app.route("/inventory/receive/<order_code>", methods=["GET", "POST"])
@login_required
def receive_order(order_code):
    return order_receive_order(order_code)

@app.route("/cost/register/<order_code>", methods=["GET", "POST"])
@login_required
def register_cost(order_code):
    return cost_register_cost(order_code)

@app.route("/cost/history")
@login_required
def view_cost_history():
    return cost_view_cost_history()

@app.route("/sales/upload", methods=["GET", "POST"])
@login_required
def upload_sales_volume():
    return sales_upload_sales_volume()

@app.route("/sales/upload_stock", methods=["GET", "POST"])
@login_required
def upload_real_stock():
    return stock_upload_real_stock()

@app.route("/sales/overview")
@login_required
def sales_overview():
    return sales_sales_overview()

@app.route('/api/product_info')
@login_required
def api_product_info():
    return product_info()

from schedule_routes import schedule_bp
app.register_blueprint(schedule_bp)


@app.route("/health/db")
def health_db():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify(status="ok", db="connected")
    except Exception as e:
        return jsonify(status="error", detail=str(e)), 500


@app.route("/init-db")
def init_db():
    create_table()
    create_inventory_table()
    create_inventory_movement_table()
    create_supplier_table()
    create_user_table()
    create_cost_history_table()
    create_order_table()
    create_sales_volume_table()
    create_real_stock_table()
    create_schedule_table()
    create_cost_expense_table()
    initialize_cost_expense_table()
    return "✅ DB 초기화가 완료되었습니다."



#if __name__ == "__main__":
#    create_table()
#    create_inventory_table()
#    create_inventory_movement_table()
#    create_supplier_table()
#    create_user_table()
#    create_cost_history_table()
#    create_order_table()
#    create_sales_volume_table()
#    create_real_stock_table()
#    add_english_name_column()
   # app.run(debug=True)
