# db.py
import os
import psycopg2

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
    return psycopg2.connect(db_url)
