import psycopg2
import psycopg2.extras
from flask import request, render_template, redirect, url_for, jsonify, flash
import io
import csv
from db import get_db_connection


CATEGORY_DATA = {
    "농산품": {
        "code": "A",
        "sub": {
            "쌀, 잡곡": 1,
            "나물, 채소": 2,
            "건어물": 3,
            "신선채소, 과일": 4
        }
    },
    "조미료": {
        "code": "B",
        "sub": {
            "장류": 1,
            "조미료": 2,
            "분말식품": 3
        }
    },
    "즉석식품": {
        "code": "C",
        "sub": {
            "면류": 1,
            "봉지라면": 2,
            "컵라면": 3,
            "즉석식품": 4,
            "통조림": 5
        }
    },
    "음료": {
        "code": "D",
        "sub": {
            "음료": 1,
            "차, 커피": 2,
            "주류": 3
        }
    },
    "간식": {
        "code": "F",
        "sub": {
            "과자": 1,
            "빵, 떡": 2,
            "사탕, 젤리 등": 3
        }
    },
    "냉장식품": {
        "code": "K",
        "sub": {
            "김치": 1,
            "두부": 2,
            "떡": 3,
            "기타": 4
        }
    },
    "냉동식품": {
        "code": "T",
        "sub": {
            "냉동즉석식품": 1,
            "만두": 2,
            "어묵": 3,
            "냉동떡": 4,
            "아이스크림": 5,
            "냉동면": 6,
            "해물, 육류": 7,
            "밀키트": 8
        }
    },
    "다와요푸드": {
        "code": "X",
        "sub": {
            "반찬": 1,
            "시니어푸드": 2
        }
    },
    "잡화": {
        "code": "Y",
        "sub": {
            "비식품": 1
        }
    },
    "도매상품": {
        "code": "Z",
        "sub": {
            "도매상품": 1
        }
    }
}


CATEGORY_SUFFIX_OPTIONS = ["세일상품", "Pfand 상품", "박스상품"]
SUFFIX_CODE_MAP = {
    "세일상품": "-S",
    "Pfand 상품": "-P",
    "박스상품": "-B"
}

def generate_sku(category_main, category_sub, suffix):
    main_code = CATEGORY_DATA[category_main]["code"]
    sub_code = CATEGORY_DATA[category_main]["sub"].get(category_sub)

    if sub_code is None:
        raise ValueError("유효하지 않은 소분류입니다.")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    for i in range(1, 10000):
        serial = f"{i:04}"
        sku = f"{main_code}{sub_code}{serial}"
        if suffix in ["-S", "-P", "-B"]:
            sku += suffix

        cursor.execute("SELECT 1 FROM products WHERE sku = %s", (sku,))
        if not cursor.fetchone():
            conn.close()
            return sku

    conn.close()
    raise ValueError("사용 가능한 SKU 번호가 없습니다.")

def create_table():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            english_name TEXT NOT NULL,
            category_main TEXT NOT NULL,
            category_sub TEXT NOT NULL,
            category_suffix TEXT,
            barcode TEXT
        )
    """)
    conn.commit()
    conn.close()

def register_product():
    if request.method == "POST":
        name = request.form.get("name")
        english_name = request.form.get("english_name")
        category_main = request.form.get("category_main")
        category_sub = request.form.get("category_sub")
        category_suffix = request.form.get("category_suffix")
        barcode = request.form.get("barcode")

        # Suffix 코드 변환
        category_suffix = SUFFIX_CODE_MAP.get(category_suffix, category_suffix)

        # 중복 바코드 검사
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM products WHERE barcode = %s", (barcode,))
        existing = cursor.fetchall()
        conn.close()

        if existing and not request.form.get("force_submit"):
            # 동일 바코드 존재함 → 사용자 확인 필요
            return render_template(
                "confirm_register.html",
                existing=existing,
                name=name,
                english_name=english_name,
                category_main=category_main,
                category_sub=category_sub,
                category_suffix=category_suffix,
                barcode=barcode,
                categories=CATEGORY_DATA,
                category_suffix_options=CATEGORY_SUFFIX_OPTIONS
            )

        # SKU 생성
        sku = generate_sku(category_main, category_sub, category_suffix)

        # 실제 등록
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            INSERT INTO products (
                sku, name, english_name, category_main,
                category_sub, category_suffix, barcode
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            sku, name, english_name, category_main,
            category_sub, category_suffix, barcode
        ))
        conn.commit()
        conn.close()

        return f"<h2>제품 '{name}' 등록 완료!<br>자동 SKU: {sku}</h2>"

    return render_template(
        "product_form.html",
        categories=CATEGORY_DATA,
        category_suffix=CATEGORY_SUFFIX_OPTIONS,
        suffix_code_map={
            "세일상품": "-S",
            "Pfand 상품": "-P",
            "박스상품": "-B"
        }
    )

def edit_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        # 수정된 정보 받기
        name = request.form.get("name")
        english_name = request.form.get("english_name")
        category_main = request.form.get("category_main")
        category_sub = request.form.get("category_sub")
        category_suffix = request.form.get("category_suffix")
        barcode = request.form.get("barcode")

        # DB 업데이트
        cursor.execute("""
            UPDATE products
            SET name = %s, english_name = %s, category_main = %s, 
                category_sub = %s, category_suffix = %s, barcode = %s
            WHERE id = %s
        """, (name, english_name, category_main, category_sub, category_suffix, barcode, product_id))
        conn.commit()
        conn.close()

        return redirect(url_for("manage_products", success=f"'{name}' 수정 완료"))

    # GET 요청: 기존 데이터 조회
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        return "<h2>존재하지 않는 제품입니다.</h2>"

    return render_template(
        "edit_product.html",
        product=product,
        categories=CATEGORY_DATA,
        category_suffix=CATEGORY_SUFFIX_OPTIONS,
        suffix_code_map={
            "세일상품": "-S",
            "Pfand 상품": "-P",
            "박스상품": "-B"
        }
    )
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("manage_products"))

def view_products():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    conn.close()

    return render_template(
        "manage_products.html",
        products=products,
        categories=CATEGORY_DATA,
        category_suffix=CATEGORY_SUFFIX_OPTIONS,
        suffix_code_map={
            "세일상품": "-S",
            "Pfand 상품": "-P",
            "박스상품": "-B"
        }
    )

def product_search():
    query = request.args.get("query", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""
        SELECT sku, name, barcode FROM products 
        WHERE sku ILIKE %s OR barcode ILIKE %s OR name ILIKE %s
        LIMIT 10
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"results": results}

def product_info():
    identifier = request.args.get("identifier", "").strip()
    if not identifier:
        return jsonify(results=[])

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""
        SELECT sku, name, english_name, barcode
        FROM products
        WHERE sku ILIKE %s OR barcode ILIKE %s OR name ILIKE %s
        LIMIT 10
    """, (f"%{identifier}%", f"%{identifier}%", f"%{identifier}%"))
    rows = cursor.fetchall()
    conn.close()

    results = [dict(row) for row in rows]
    return jsonify(results=results)

def manage_products():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    message = request.args.get("success")

    if request.method == "POST":
        if "csv_file" in request.files:
            file = request.files["csv_file"]
            if file.filename == '':
                flash('CSV 파일을 선택해주세요.')
                conn.close()
                return redirect(request.url)

            try:
                import io, csv
                stream = io.StringIO(file.stream.read().decode("utf-8"))
                reader = csv.DictReader(stream, delimiter=';')
                reader.fieldnames = [f.strip().replace('\ufeff', '') for f in reader.fieldnames]
                sku_tracker = {}

                for row in reader:
                    name = row.get("제품명")
                    english_name = row.get("영문명")
                    category_main = row.get("대분류")
                    category_sub = row.get("소분류")
                    barcode = row.get("바코드", "").strip()
                    suffix_raw = row.get("접미사")              # 먼저 값을 가져오고
                    suffix_raw = suffix_raw.strip() if suffix_raw else ""  # 안전하게 strip 
                    category_suffix = SUFFIX_CODE_MAP.get(suffix_raw, "")
                    print("📌 ROW:", row)
                    print("📌 category_main:", row.get("대분류"), "category_sub:", row.get("소분류"))
                    print("📌 fieldnames:", reader.fieldnames)

                    if not (name and english_name and category_main and category_sub):
                        print(f"⚠️ 필수값 누락: {row}")
                        continue

                    try:
                        main_code = CATEGORY_DATA[category_main]["code"]
                        sub_code = CATEGORY_DATA[category_main]["sub"][category_sub]
                    except KeyError:
                        print(f"❌ 분류 코드 매핑 실패: {category_main} / {category_sub}")
                        continue

                    key = (category_main, category_sub, category_suffix)
                    if key not in sku_tracker:
                        cursor.execute("""
                            SELECT COUNT(*) FROM products
                            WHERE category_main = %s AND category_sub = %s AND category_suffix = %s
                        """, (category_main, category_sub, category_suffix))
                        count = cursor.fetchone()[0]
                        sku_tracker[key] = count + 1

                    serial = f"{sku_tracker[key]:04}"
                    sku = f"{main_code}{sub_code}{serial}"
                    if category_suffix in ["-S", "-P", "-B"]:
                        sku += category_suffix
                    sku_tracker[key] += 1

                    cursor.execute("""
                        INSERT INTO products
                        (sku, name, english_name, category_main, category_sub, category_suffix, barcode)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sku) DO NOTHING
                    """, (sku, name, english_name, category_main, category_sub, category_suffix, barcode))

                    if cursor.rowcount == 0:
                        print(f"⚠️ 중복 무시됨: {sku}")
                    else:
                        print(f"✅ 등록됨: {sku}")

                conn.commit()
                flash("CSV 대량 등록이 완료되었습니다.")
            except Exception as e:
                flash(f"CSV 업로드 중 오류 발생: {e}")
            finally:
                conn.close()

            return redirect(url_for("manage_products"))

        else:
            name = request.form.get("name")
            english_name = request.form.get("english_name")
            category_main = request.form.get("category_main")
            category_sub = request.form.get("category_sub")
            category_suffix_raw = request.form.get("category_suffix")
            barcode = request.form.get("barcode")
            force_submit = request.form.get("force_submit")

            if not (name and english_name and category_main and category_sub):
                message = "❌ 필수 항목이 누락되었습니다."
            else:
                category_suffix = SUFFIX_CODE_MAP.get(category_suffix_raw, category_suffix_raw)
                cursor.execute("SELECT * FROM products WHERE barcode = %s", (barcode,))
                existing = cursor.fetchall()

                if existing and not force_submit:
                    message = f"""
                    ⚠️ 동일한 바코드를 가진 제품이 이미 존재합니다: {barcode}<br><br>
                    <form method="post">
                        <input type="hidden" name="name" value="{name}">
                        <input type="hidden" name="english_name" value="{english_name}">
                        <input type="hidden" name="category_main" value="{category_main}">
                        <input type="hidden" name="category_sub" value="{category_sub}">
                        <input type="hidden" name="category_suffix" value="{category_suffix_raw}">
                        <input type="hidden" name="barcode" value="{barcode}">
                        <input type="hidden" name="force_submit" value="1">
                        <button type="submit">✅ 그래도 등록하겠습니다</button>
                        <a href="{url_for('manage_products')}">❌ 취소</a>
                    </form>
                    """
                else:
                    try:
                        sku = generate_sku(category_main, category_sub, category_suffix)
                        cursor.execute("""
                            INSERT INTO products (
                                sku, name, english_name, category_main,
                                category_sub, category_suffix, barcode
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            sku, name, english_name, category_main,
                            category_sub, category_suffix, barcode
                        ))
                        conn.commit()
                        message = f"✅ 제품 등록 완료: {name} (SKU: {sku})"
                    except Exception as e:
                        message = f"❌ 등록 실패: {e}"

    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    conn.close()

    return render_template(
        "manage_products.html",
        products=products,
        categories=CATEGORY_DATA,
        category_suffix=CATEGORY_SUFFIX_OPTIONS,
        suffix_code_map=SUFFIX_CODE_MAP,
        message=message
    )