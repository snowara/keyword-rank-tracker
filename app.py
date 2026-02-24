"""네이버 쇼핑 키워드 순위 트래커 — Streamlit 앱"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from core.db_manager import init_db
from core.scheduler import init_scheduler_from_settings, is_running

# ── 페이지 설정 ──
st.set_page_config(
    page_title="키워드 순위 트래커",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── DB 초기화 ──
init_db()

# ── 스케줄러 복원 (세션 당 1회) ──
if "scheduler_initialized" not in st.session_state:
    init_scheduler_from_settings()
    st.session_state.scheduler_initialized = True

# ── 커스텀 CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 500;
    }
    div[data-testid="stMetric"] {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label { font-size: 13px; color: #666; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 28px; font-weight: 700; color: #1B2A4A;
    }
</style>
""", unsafe_allow_html=True)

# ── 헤더 ──
hcol1, hcol2 = st.columns([5, 1])
with hcol1:
    st.title("📊 네이버 쇼핑 키워드 순위 트래커")
    st.caption("스노우아라 — 키워드별 순위 추적 · 변동 알림 · 이력 분석")
with hcol2:
    scheduler_status = "🟢 스케줄 ON" if is_running() else "⚪ 스케줄 OFF"
    st.markdown(f"<div style='text-align:right;padding-top:20px;color:#666;font-size:13px'>{scheduler_status}</div>", unsafe_allow_html=True)

# ── 탭 ──
from pages import dashboard, keyword_manage, rank_history, settings

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 대시보드",
    "🔑 키워드 관리",
    "📋 순위 이력",
    "⚙️ 설정",
])

with tab1:
    dashboard.render()
with tab2:
    keyword_manage.render()
with tab3:
    rank_history.render()
with tab4:
    settings.render()
