# config.py

import os
from dotenv import load_dotenv
from datetime import timedelta

# .env 파일의 환경변수를 불러옵니다.
load_dotenv()

class Config:
    # 세션 암호화 키
    SECRET_KEY = os.getenv('SECRET_KEY')
    # SQLite 파일 기반 DB 연결 문자열
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    # 세션 유지 기간 (7일)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
