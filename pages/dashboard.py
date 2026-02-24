"""탭1: 대시보드 — 요약 메트릭 + 순위 테이블 + 추이 차트"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.db_manager import get_latest_ranks, get_all_rank_history, get_setting


def render():
    latest = get_latest_ranks()

    if not latest:
        st.info("등록된 키워드가 없습니다. **키워드 관리** 탭에서 키워드를 등록해주세요.")
        return

    # ── 메트릭 카드 ──
    total = len(latest)
    ranked = [r for r in latest if r["rank"] is not None]
    avg_rank = sum(r["rank"] for r in ranked) / len(ranked) if ranked else 0
    top10 = len([r for r in ranked if r["rank"] <= 10])
    improved = 0
    for r in latest:
        if r["rank"] is not None and r["prev_rank"] is not None:
            if r["rank"] < r["prev_rank"]:
                improved += 1

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("추적 키워드", f"{total}개")
    m2.metric("평균 순위", f"{avg_rank:.0f}위" if ranked else "-")
    m3.metric("TOP 10", f"{top10}개")
    m4.metric("순위 상승", f"{improved}개")

    last_check = get_setting("last_check_time", "체크 기록 없음")
    st.caption(f"최근 체크: {last_check}")

    st.divider()

    # ── 전체 순위 테이블 ──
    st.subheader("현재 순위 현황")

    table_data = []
    for r in latest:
        rank = r["rank"]
        prev = r["prev_rank"]
        if rank and prev:
            change = prev - rank  # 양수=상승, 음수=하락
            if change > 0:
                change_str = f"▲{change}"
            elif change < 0:
                change_str = f"▼{abs(change)}"
            else:
                change_str = "-"
        elif rank and not prev:
            change_str = "NEW"
        else:
            change_str = "-"

        table_data.append({
            "키워드": r["keyword"],
            "타겟": r["target_value"],
            "현재 순위": f"{rank}위" if rank else "순위권 밖",
            "변동": change_str,
            "스토어": r.get("mall_name", "-") or "-",
            "가격": f"₩{r['price']:,}" if r.get("price") else "-",
            "체크 시각": (r.get("checked_at") or "-")[:16],
        })

    df = pd.DataFrame(table_data)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "현재 순위": st.column_config.TextColumn(width="small"),
            "변동": st.column_config.TextColumn(width="small"),
        },
    )

    st.divider()

    # ── 순위 추이 차트 ──
    st.subheader("순위 추이 (최근 30일)")

    history = get_all_rank_history(days=30)
    if not history:
        st.info("아직 순위 이력 데이터가 없습니다. 순위 체크를 실행해주세요.")
        return

    df_hist = pd.DataFrame(history)
    df_hist = df_hist[df_hist["rank"].notnull()]

    if df_hist.empty:
        st.info("순위권 내 데이터가 없습니다.")
        return

    df_hist["checked_at"] = pd.to_datetime(df_hist["checked_at"])
    df_hist["label"] = df_hist["keyword"] + " (" + df_hist["target_value"] + ")"

    fig = px.line(
        df_hist,
        x="checked_at",
        y="rank",
        color="label",
        markers=True,
        labels={"checked_at": "날짜", "rank": "순위", "label": "키워드"},
    )
    fig.update_yaxes(autorange="reversed", title="순위 (낮을수록 좋음)")
    fig.update_xaxes(title="")
    fig.update_layout(
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
