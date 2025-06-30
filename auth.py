import hashlib
from flask import request, render_template, redirect, url_for, session, flash
from functools import wraps
import psycopg2
import psycopg2.extras
from db import get_db_connection
import json



def login_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        return view_function(*args, **kwargs)
    return wrapper

def menu_required(menu_key):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if menu_key not in session.get("menus", []):
                flash("❌접근 권한이 없습니다.", "warning")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def authenticate_user(username, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, hashed_pw))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user_table():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            english_name TEXT,
            accessible_menus TEXT
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def admin_add_user():
    message = None
    current_user = session.get("user")

    if request.method == "POST" and request.form.get("action") == "add":
        username     = request.form.get("username", "").strip()
        password     = request.form.get("password", "").strip()
        name         = request.form.get("name", "").strip()
        english_name = request.form.get("english_name", "").strip()
        menus        = request.form.getlist("menus")  # 🔹 체크박스 값들 리스트로 가져옴

        if not (username and password and name and english_name):
            message = "모든 필드를 입력하세요."
        else:
            pw_hash = hash_password(password)
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, name, english_name, accessible_menus)
                    VALUES (%s, %s, %s, %s, %s)
                """, (username, pw_hash, name, english_name, json.dumps(menus)))
                conn.commit()
                message = "직원이 등록되었습니다."
            except Exception:
                message = "이미 존재하는 아이디입니다."
            finally:
                conn.close()

    if request.method == "POST" and request.form.get("action") == "delete":
        delete_id = request.form.get("user_id")
        if delete_id and int(delete_id) != session["user"]["id"]:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("DELETE FROM users WHERE id = %s", (delete_id,))
            conn.commit()
            conn.close()
            message = f"ID {delete_id} 직원이 삭제되었습니다."
        else:
            message = "본인 계정은 삭제할 수 없습니다."

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT id, username, name, english_name FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_add_user.html",
        users=users,
        message=message,
        current_user=current_user
    )

def login():
    if request.method == "POST":
        user = authenticate_user(request.form["username"], request.form["password"])
        if user:
            session["user"] = {
                "id":       user["id"],
                "username": user["username"],
                "name":     user["name"],
                "english_name":    user["english_name"]
            }
            menus = user.get("accessible_menus")
            session["menus"] = json.loads(menus) if menus else []
            next_page = request.args.get("next")
            return redirect(next_page or url_for("home"))
        else:
            error = "아이디 또는 비밀번호가 잘못되었습니다."
            return render_template("login.html", error=error)
    return render_template("login.html")


def logout():
    session.clear()
    return redirect(url_for("login"))

def admin_user_list():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT id, username, name FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()
    return render_template("admin_user_list.html", users=users)

def admin_delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_user_list"))

def admin_user_manage():
    message = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        english_name = request.form.get("english_name", "").strip()

        if not username or not password or not name or not english_name:
            message = "모든 필드를 입력하세요."
        else:
            password_hash = hash_password(password)
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, name, english_name)
                    VALUES (%s, %s, %s, %s)
                """, (username, password_hash, name, english_name))
                conn.commit()
                message = "직원이 등록되었습니다!"
            except Exception:
                message = "이미 존재하는 아이디입니다."
            finally:
                conn.close()

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT id, username, name, english_name FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()

    return render_template("admin_user_manage.html", users=users, message=message)

@login_required
def change_password():
    current = session.get("user")
    if not current:
        return redirect(url_for("login"))

    if request.method == "POST":
        old_pw     = request.form.get("old_password", "").strip()
        new_pw     = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()

        if not old_pw or not new_pw or not confirm_pw:
            flash("모든 필드를 입력하세요.", "warning")
            return redirect(url_for("change_password"))

        if new_pw != confirm_pw:
            flash("새 비밀번호와 확인이 일치하지 않습니다.", "warning")
            return redirect(url_for("change_password"))

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT password FROM users WHERE id = %s", (current["id"],))
        row = cursor.fetchone()
        conn.close()

        if not row or hash_password(old_pw) != row[0]:
            flash("기존 비밀번호가 올바르지 않습니다.", "danger")
            return redirect(url_for("change_password"))

        hashed_new = hash_password(new_pw)
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_new, current["id"]))
        conn.commit()
        conn.close()

        flash("비밀번호가 성공적으로 변경되었습니다.", "success")
        return redirect(url_for("home"))

    return render_template("change_password.html")
