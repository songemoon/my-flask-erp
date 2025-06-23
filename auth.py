import sqlite3
import hashlib
from flask import request, render_template, redirect, url_for, session
from functools import wraps

def login_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        return view_function(*args, **kwargs)
    return wrapper

def authenticate_user(username, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_pw))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user_table():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            english_name TEXT  -- 이 컬럼을 추가하세요
        )
    """)
    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def admin_add_user():
    message = None
    current_user = session.get("user")

    # 1) POST 요청: 직원 등록
    if request.method == "POST" and request.form.get("action") == "add":
        username     = request.form.get("username", "").strip()
        password     = request.form.get("password", "").strip()
        name         = request.form.get("name", "").strip()
        english_name = request.form.get("english_name", "").strip()

        if not (username and password and name and english_name):
            message = "모든 필드를 입력하세요."
        else:
            pw_hash = hash_password(password)
            conn    = sqlite3.connect("database.db")
            cursor  = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, name, english_name)
                    VALUES (?, ?, ?, ?)
                """, (username, pw_hash, name, english_name))
                conn.commit()
                message = "직원이 등록되었습니다."
            except sqlite3.IntegrityError:
                message = "이미 존재하는 아이디입니다."
            finally:
                conn.close()

    # 2) POST 요청: 직원 삭제
    if request.method == "POST" and request.form.get("action") == "delete":
        delete_id = request.form.get("user_id")
        if delete_id and int(delete_id) != session["user"]["id"]:
            conn   = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (delete_id,))
            conn.commit()
            conn.close()
            message = f"ID {delete_id} 직원이 삭제되었습니다."
        else:
            message = "본인 계정은 삭제할 수 없습니다."

    # 3) 직원 목록 조회 (GET 또는 POST 후)
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
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
            session["user"] = {"id": user["id"], "username": user["username"], "name": user["name"], "english_name": user["english_name"]}
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect(url_for("home"))
        else:
            error = "아이디 또는 비밀번호가 잘못되었습니다."
            return render_template("login.html", error=error)
    return render_template("login.html")

from flask import session, redirect, url_for

def logout():
    session.clear()
    return redirect(url_for("login"))

def admin_user_list():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, name FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()
    return render_template("admin_user_list.html", users=users)

def admin_delete_user(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_user_list"))  # 직원 목록 페이지로 리디렉션 (페이지명은 상황에 맞게)

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
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, name, english_name)
                    VALUES (?, ?, ?, ?)
                """, (username, password_hash, name, english_name))
                conn.commit()
                message = "직원이 등록되었습니다!"
            except sqlite3.IntegrityError:
                message = "이미 존재하는 아이디입니다."
            finally:
                conn.close()

    # 직원 목록 조회 (GET 또는 POST 직후)
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, name, english_name FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()

    return render_template("admin_user_manage.html", users=users, message=message)


from flask import request, render_template, redirect, url_for, session, flash

@login_required
def change_password():
    current = session.get("user")
    if not current:
        return redirect(url_for("login"))

    if request.method == "POST":
        old_pw    = request.form.get("old_password", "").strip()
        new_pw    = request.form.get("new_password", "").strip()
        confirm_pw= request.form.get("confirm_password", "").strip()

        # 1) 입력 검증
        if not old_pw or not new_pw or not confirm_pw:
            flash("모든 필드를 입력하세요.", "warning")
            return redirect(url_for("change_password"))

        if new_pw != confirm_pw:
            flash("새 비밀번호와 확인이 일치하지 않습니다.", "warning")
            return redirect(url_for("change_password"))

        # 2) 기존 비밀번호 확인
        conn   = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cur    = conn.cursor()
        cur.execute("SELECT password FROM users WHERE id = ?", (current["id"],))
        row    = cur.fetchone()
        conn.close()

        if not row or hash_password(old_pw) != row["password"]:
            flash("기존 비밀번호가 올바르지 않습니다.", "danger")
            return redirect(url_for("change_password"))

        # 3) 비밀번호 업데이트
        hashed_new = hash_password(new_pw)
        conn   = sqlite3.connect("database.db")
        cur    = conn.cursor()
        cur.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new, current["id"]))
        conn.commit()
        conn.close()

        flash("비밀번호가 성공적으로 변경되었습니다.", "success")
        return redirect(url_for("home"))

    # GET 요청: 폼 렌더링
    return render_template("change_password.html")
