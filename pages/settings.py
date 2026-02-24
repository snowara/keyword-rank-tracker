"""탭4: 설정 — 스케줄, 알림 조건, Gmail SMTP, DB 관리"""
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import DB_PATH
from core.db_manager import get_setting, set_setting, get_alert_logs
from core.scheduler import start_scheduler, stop_scheduler, is_running
from core.alert_sender import send_alert


def render():
    st.header("설정")

    col_left, col_right = st.columns(2)

    # ── 스케줄 설정 ──
    with col_left:
        st.subheader("자동 스케줄")

        scheduler_on = is_running()
        st.markdown(f"현재 상태: **{'🟢 실행 중' if scheduler_on else '⚪ 중지'}**")

        hour = int(get_setting("scheduler_hour", "9"))
        minute = int(get_setting("scheduler_minute", "0"))

        c1, c2 = st.columns(2)
        with c1:
            new_hour = st.number_input("실행 시각 (시)", min_value=0, max_value=23, value=hour)
        with c2:
            new_minute = st.number_input("실행 시각 (분)", min_value=0, max_value=59, value=minute, step=10)

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("스케줄 시작" if not scheduler_on else "스케줄 재시작",
                         type="primary", use_container_width=True):
                start_scheduler(int(new_hour), int(new_minute))
                st.success(f"스케줄 시작: 매일 {int(new_hour):02d}:{int(new_minute):02d}")
                st.rerun()
        with bcol2:
            if st.button("스케줄 중지", use_container_width=True, disabled=not scheduler_on):
                stop_scheduler()
                st.info("스케줄 중지됨")
                st.rerun()

        last_check = get_setting("last_check_time", "없음")
        st.caption(f"마지막 체크: {last_check}")

    # ── 알림 조건 ──
    with col_right:
        st.subheader("알림 조건")

        alerts_enabled = get_setting("alerts_enabled", "0") == "1"
        new_alerts = st.toggle("이메일 알림 활성화", value=alerts_enabled)

        threshold = int(get_setting("alert_threshold", "5"))
        new_threshold = st.number_input("순위 변동 알림 기준 (N단계 이상)", min_value=1, max_value=50, value=threshold)

        alert_top10 = get_setting("alert_top10", "1") == "1"
        new_top10 = st.checkbox("TOP 10 진입/이탈 알림", value=alert_top10)

        alert_lost = get_setting("alert_lost", "1") == "1"
        new_lost = st.checkbox("순위 이탈 알림", value=alert_lost)

        alert_new = get_setting("alert_new", "1") == "1"
        new_new = st.checkbox("신규 진입 알림", value=alert_new)

        if st.button("알림 설정 저장", use_container_width=True):
            set_setting("alerts_enabled", "1" if new_alerts else "0")
            set_setting("alert_threshold", str(new_threshold))
            set_setting("alert_top10", "1" if new_top10 else "0")
            set_setting("alert_lost", "1" if new_lost else "0")
            set_setting("alert_new", "1" if new_new else "0")
            st.success("알림 설정 저장 완료")

    st.divider()

    # ── Gmail SMTP 설정 ──
    st.subheader("Gmail SMTP 설정")
    st.caption("Gmail 앱 비밀번호가 필요합니다. [Google 앱 비밀번호 설정](https://myaccount.google.com/apppasswords)")

    gcol1, gcol2 = st.columns(2)
    with gcol1:
        gmail_addr = st.text_input(
            "Gmail 주소",
            value=get_setting("gmail_address", ""),
            placeholder="your@gmail.com",
        )
        gmail_pw = st.text_input(
            "앱 비밀번호",
            value=get_setting("gmail_app_password", ""),
            type="password",
        )
    with gcol2:
        recipient = st.text_input(
            "알림 수신 이메일",
            value=get_setting("alert_recipient", ""),
            placeholder="recipient@example.com",
        )

    smtp_col1, smtp_col2 = st.columns(2)
    with smtp_col1:
        if st.button("SMTP 설정 저장", use_container_width=True):
            set_setting("gmail_address", gmail_addr)
            set_setting("gmail_app_password", gmail_pw)
            set_setting("alert_recipient", recipient)
            st.success("SMTP 설정 저장 완료")
    with smtp_col2:
        if st.button("테스트 이메일 발송", use_container_width=True):
            # 임시 저장
            set_setting("gmail_address", gmail_addr)
            set_setting("gmail_app_password", gmail_pw)
            set_setting("alert_recipient", recipient)
            test_alert = [{
                "keyword": "테스트 키워드",
                "keyword_id": 0,
                "rank": 5,
                "prev_rank": 12,
                "change": -7,
                "alert_type": "테스트 알림",
            }]
            success = send_alert(test_alert)
            if success:
                st.success("테스트 이메일 발송 완료!")
            else:
                st.error("발송 실패 — SMTP 설정을 확인해주세요.")

    st.divider()

    # ── 알림 로그 ──
    st.subheader("최근 알림 로그")
    logs = get_alert_logs(limit=20)
    if logs:
        for log in logs:
            st.text(f"[{log['sent_at']}] {log.get('keyword','')} — {log['alert_type']}: {log['message']}")
    else:
        st.caption("알림 로그가 없습니다.")

    st.divider()

    # ── DB 관리 ──
    st.subheader("데이터 관리")

    db_col1, db_col2 = st.columns(2)
    with db_col1:
        if DB_PATH.exists():
            size_mb = DB_PATH.stat().st_size / (1024 * 1024)
            st.caption(f"DB 파일: {DB_PATH.name} ({size_mb:.2f} MB)")

            with open(str(DB_PATH), "rb") as f:
                st.download_button(
                    "💾 DB 백업 다운로드",
                    data=f.read(),
                    file_name=f"tracker_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream",
                    use_container_width=True,
                )
    with db_col2:
        st.caption("DB 파일을 백업한 후 초기화할 수 있습니다.")
        if st.button("⚠️ DB 초기화", use_container_width=True):
            st.warning("정말 DB를 초기화하시겠습니까? 모든 데이터가 삭제됩니다.")
            if st.button("확인 — DB 초기화 실행", type="primary"):
                if DB_PATH.exists():
                    DB_PATH.unlink()
                from core.db_manager import init_db
                init_db()
                st.success("DB 초기화 완료")
                st.rerun()
