# -*- coding: utf-8 -*-
"""
보안 설정 파일
관리자 정보와 시스템 설정을 안전하게 관리합니다.
"""

import os
from datetime import timedelta


class Config:
    # 기본 Flask 설정
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sk_ons_warehouse_secret_key_2025_secure'

    # 데이터베이스 설정
    DATABASE_PATH = 'warehouse.db'

    # 파일 업로드 설정
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # 세션 설정
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # 8시간 후 자동 로그아웃

    # 도메인 설정
    DOMAIN_NAME = 'storageborame.net'
    PORT = 5000

    # 보안 설정
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False  # HTTPS 사용시 True로 변경
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class AdminConfig:
    """
    관리자 설정 - 초기 설정용
    실제 운영시에는 환경변수나 별도 파일로 관리 권장
    """
    # 초기 관리자 계정 (첫 실행시에만 사용)
    ADMIN_ID = 'admin'
    ADMIN_PASSWORD = 'Onsn1103813!'  # 첫 로그인 후 반드시 변경 필요

    # 팀 목록
    TEAMS = ['설비', '강남', '강동', '관악', '양천']

    # 창고 목록
    WAREHOUSES = {
        '보라매창고': {'status': 'active', 'categories': ['전기차', 'Access']},
        '관악창고': {'status': 'preparing', 'categories': []},
        '강남창고': {'status': 'preparing', 'categories': []},
        '강동창고': {'status': 'preparing', 'categories': []},
        '양천창고': {'status': 'preparing', 'categories': []}
    }


class SecurityConfig:
    """보안 관련 설정"""

    # 비밀번호 정책
    MIN_PASSWORD_LENGTH = 8
    PASSWORD_COMPLEXITY = False  # True시 대소문자, 숫자, 특수문자 조합 필수

    # 로그인 시도 제한
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_ATTEMPT_TIMEOUT = 300  # 5분

    # 세션 보안
    REGENERATE_SESSION_ON_LOGIN = True

    # 파일 업로드 보안
    SCAN_UPLOADED_FILES = True
    MAX_FILE_SIZE_KB = 10240  # 10MB

    # 데이터 보관 정책
    HISTORY_RETENTION_DAYS = 14  # 2주
    LOG_RETENTION_DAYS = 30  # 1개월


# 환경별 설정
class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # HTTPS 필수


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


# 현재 환경 설정
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}