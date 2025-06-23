#!/usr/bin/env python3
import sqlite3

DB_PATH = "database.db"

def list_all_users():
    """
    모든 직원의 ID, username, name, english_name을 출력합니다.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, username, name, english_name FROM users ORDER BY id")
    users = cur.fetchall()
    conn.close()

    print("=== 직원 목록 ===")
    if not users:
        print("등록된 직원이 없습니다.")
    else:
        for u in users:
            print(f"ID: {u['id']:>3} | 아이디: {u['username']:<15} | 이름: {u['name']:<10} | 영문이름: {u['english_name']}")
    print("=================")

def delete_user_by_id(user_id: int) -> bool:
    """
    주어진 user_id의 계정을 삭제합니다.
    반환: 삭제 성공(True) / 해당 ID 없음(False)
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
    exists = cur.fetchone()[0]
    if not exists:
        conn.close()
        return False

    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    # 1) 직원 목록 출력
    list_all_users()

    # 2) 사용자 입력
    try:
        target = int(input("삭제할 직원의 ID를 입력하세요: ").strip())
    except ValueError:
        print("⚠️ 잘못된 입력입니다. 숫자만 입력해주세요.")
        exit(1)

    # 3) 삭제 처리
    if delete_user_by_id(target):
        print(f"✅ 직원 ID {target} 삭제 완료")
    else:
        print(f"⚠️ 해당 ID({target})의 직원이 없습니다.")
