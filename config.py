import os
from dotenv import load_dotenv
from datetime import timedelta

# .env 파일 로드
load_dotenv()

class Config:
    # Flask 세션용 비밀 키
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # PostgreSQL 접속용 URL (psycopg2에서 직접 사용)
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # 로그인 세션 유지 시간
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
