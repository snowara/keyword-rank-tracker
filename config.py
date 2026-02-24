"""환경변수 및 상수 설정 — 로컬(.env) + Streamlit Cloud(secrets) 지원"""
import os
from pathlib import Path

# ── 환경변수 로드 (로컬 .env → st.secrets 순) ──
try:
    from dotenv import load_dotenv
    ENV_PATH = Path(__file__).resolve().parent / ".env"
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
except ImportError:
    pass


def _get_secret(key: str, default: str = "") -> str:
    """로컬 env → st.secrets 순으로 시크릿 조회"""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# 네이버 API
NAVER_CLIENT_ID = _get_secret("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _get_secret("NAVER_CLIENT_SECRET")

# 네이버 쇼핑 API
NAVER_SHOP_API_URL = "https://openapi.naver.com/v1/search/shop.json"
NAVER_API_HEADERS = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
}

# 순위 체크 설정
MAX_PAGES = 10           # 최대 탐색 페이지 (100건 × 10 = 1000위)
ITEMS_PER_PAGE = 100     # 페이지당 항목 수
RATE_LIMIT_DELAY = 0.12  # API 호출 간 대기 (초)
REQUEST_TIMEOUT = 15     # 요청 타임아웃 (초)
MAX_RETRIES = 3          # 최대 재시도 횟수
EARLY_STOP_PAGES = 2     # 매칭 발견 후 연속 미발견 시 중단 페이지 수

# DB
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "tracker.db"

# 정렬 옵션
SORT_OPTIONS = {
    "sim": "정확도순",
    "date": "날짜순",
    "asc": "가격낮은순",
    "dsc": "가격높은순",
}
