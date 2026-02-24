"""탭2: 키워드/스토어 등록 관리"""
import streamlit as st
import pandas as pd

from config import SORT_OPTIONS
from core.db_manager import (
    get_keywords, add_keyword, update_keyword, delete_keyword,
    add_rank_record, get_latest_ranks,
)
from core.rank_checker import check_rank, check_all_keywords


def render():
    st.header("키워드 관리")

    # ── 키워드 등록 ──
    with st.expander("➕ 새 키워드 등록", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_keyword = st.text_input("검색 키워드", placeholder="예: 판촉물 텀블러")
            target_type = st.selectbox(
                "매칭 기준",
                options=["mall", "title", "both"],
                format_func=lambda x: {"mall": "스토어명", "title": "상품명", "both": "스토어명+상품명"}[x],
            )
        with col2:
            target_value = st.text_input("매칭 값", placeholder="예: 스노우아라")
            sort_type = st.selectbox(
                "정렬 기준",
                options=list(SORT_OPTIONS.keys()),
                format_func=lambda x: SORT_OPTIONS[x],
            )

        if st.button("등록", type="primary", use_container_width=True):
            if not new_keyword or not target_value:
                st.error("키워드와 매칭 값을 모두 입력해주세요.")
            else:
                add_keyword(new_keyword, target_type, target_value, sort_type)
                st.success(f"키워드 등록 완료: **{new_keyword}**")
                st.rerun()

    st.divider()

    # ── 등록된 키워드 목록 ──
    keywords = get_keywords()
    if not keywords:
        st.info("등록된 키워드가 없습니다. 위에서 키워드를 등록해주세요.")
        return

    # 최신 순위 정보 병합
    latest = {r["keyword_id"]: r for r in get_latest_ranks()}

    st.subheader(f"등록 키워드 ({len(keywords)}개)")

    # 일괄 체크 버튼
    col_batch1, col_batch2 = st.columns([1, 3])
    with col_batch1:
        if st.button("🔄 전체 순위 체크", use_container_width=True):
            active_kws = [kw for kw in keywords if kw["is_active"]]
            if not active_kws:
                st.warning("활성 키워드가 없습니다.")
            else:
                progress = st.progress(0, text="순위 체크 중...")

                def on_progress(current, total, kw_name):
                    pct = current / total if total > 0 else 1.0
                    progress.progress(pct, text=f"체크 중: {kw_name} ({current}/{total})")

                results = check_all_keywords(active_kws, progress_callback=on_progress)
                for cr in results:
                    r = cr["result"]
                    add_rank_record(
                        keyword_id=cr["keyword_id"],
                        rank=r.rank, title=r.title, mall_name=r.mall_name,
                        price=r.price, link=r.link, product_id=r.product_id,
                    )
                progress.empty()
                st.success(f"전체 순위 체크 완료: {len(results)}건")
                st.rerun()

    # 키워드 테이블
    for kw in keywords:
        kid = kw["id"]
        lr = latest.get(kid, {})
        rank = lr.get("rank")
        rank_display = f"**{rank}위**" if rank else "순위권 밖"
        status = "🟢" if kw["is_active"] else "⚪"
        type_label = {"mall": "스토어", "title": "상품명", "both": "복합"}[kw["target_type"]]

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 1, 2])
            with c1:
                st.markdown(f"{status} **{kw['keyword']}**")
                st.caption(f"{type_label}: {kw['target_value']} | {SORT_OPTIONS.get(kw['sort_type'], kw['sort_type'])}")
            with c2:
                st.metric("현재 순위", rank_display.replace("**", ""))
            with c3:
                checked = lr.get("checked_at", "-")
                if checked and checked != "-":
                    checked = checked[5:16]  # MM-DD HH:MM
                st.caption(f"체크: {checked}")

            with c4:
                bcol1, bcol2, bcol3 = st.columns(3)
                with bcol1:
                    if st.button("🔍", key=f"test_{kid}", help="테스트 검색"):
                        with st.spinner("검색 중..."):
                            result = check_rank(
                                kw["keyword"], kw["target_type"],
                                kw["target_value"], kw["sort_type"],
                                max_pages=3,
                            )
                        if result.rank:
                            st.success(f"{result.rank}위 | {result.mall_name} | ₩{result.price:,}")
                        else:
                            st.warning(f"순위권 밖 (상위 {result.total_searched}개 탐색)")
                with bcol2:
                    active_label = "⏸" if kw["is_active"] else "▶"
                    if st.button(active_label, key=f"toggle_{kid}", help="활성/비활성 토글"):
                        update_keyword(kid, is_active=0 if kw["is_active"] else 1)
                        st.rerun()
                with bcol3:
                    if st.button("🗑", key=f"del_{kid}", help="삭제"):
                        delete_keyword(kid)
                        st.rerun()
