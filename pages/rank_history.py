"""탭3: 순위 이력 상세 — 키워드별 차트 + 이력 테이블 + 통계 + CSV 다운로드"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.db_manager import get_keywords, get_rank_history


def render():
    st.header("순위 이력")

    keywords = get_keywords()
    if not keywords:
        st.info("등록된 키워드가 없습니다.")
        return

    # 키워드 선택
    kw_options = {kw["id"]: f"{kw['keyword']} ({kw['target_value']})" for kw in keywords}
    selected_id = st.selectbox(
        "키워드 선택",
        options=list(kw_options.keys()),
        format_func=lambda x: kw_options[x],
    )

    # 기간 선택
    days = st.select_slider("조회 기간", options=[7, 14, 30, 60, 90], value=30, format_func=lambda x: f"{x}일")

    history = get_rank_history(selected_id, days=days)

    if not history:
        st.warning("선택한 기간에 순위 이력이 없습니다.")
        return

    df = pd.DataFrame(history)
    df["checked_at"] = pd.to_datetime(df["checked_at"])

    # ── 통계 요약 ──
    ranked_df = df[df["rank"].notnull()]
    if not ranked_df.empty:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("체크 횟수", f"{len(df)}회")
        s2.metric("평균 순위", f"{ranked_df['rank'].mean():.1f}위")
        s3.metric("최고 순위", f"{int(ranked_df['rank'].min())}위")
        s4.metric("최저 순위", f"{int(ranked_df['rank'].max())}위")
    else:
        st.metric("체크 횟수", f"{len(df)}회 (모두 순위권 밖)")

    st.divider()

    # ── 순위 추이 차트 (Y축 역전) ──
    st.subheader("순위 추이 차트")

    fig = go.Figure()

    if not ranked_df.empty:
        fig.add_trace(go.Scatter(
            x=ranked_df["checked_at"],
            y=ranked_df["rank"],
            mode="lines+markers",
            name="순위",
            line=dict(color="#1B2A4A", width=2),
            marker=dict(size=8, color="#4A6FA5"),
            hovertemplate="<b>%{x|%m/%d %H:%M}</b><br>순위: %{y}위<extra></extra>",
        ))

        # TOP 10 기준선
        fig.add_hline(y=10, line_dash="dash", line_color="#E8B931",
                      annotation_text="TOP 10", annotation_position="right")

    # 순위권 밖 표시
    out_df = df[df["rank"].isnull()]
    if not out_df.empty:
        max_rank = ranked_df["rank"].max() + 50 if not ranked_df.empty else 100
        fig.add_trace(go.Scatter(
            x=out_df["checked_at"],
            y=[max_rank] * len(out_df),
            mode="markers",
            name="순위권 밖",
            marker=dict(size=10, color="#e74c3c", symbol="x"),
            hovertemplate="<b>%{x|%m/%d %H:%M}</b><br>순위권 밖<extra></extra>",
        ))

    fig.update_yaxes(autorange="reversed", title="순위 (낮을수록 좋음)")
    fig.update_xaxes(title="")
    fig.update_layout(
        height=400,
        margin=dict(l=40, r=20, t=20, b=40),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── 이력 테이블 ──
    st.subheader("상세 이력")

    display_df = df[["checked_at", "rank", "title", "mall_name", "price", "link"]].copy()
    display_df.columns = ["체크 시각", "순위", "상품명", "스토어", "가격", "링크"]
    display_df["순위"] = display_df["순위"].apply(lambda x: f"{int(x)}위" if pd.notnull(x) else "순위권 밖")
    display_df["가격"] = display_df["가격"].apply(lambda x: f"₩{int(x):,}" if pd.notnull(x) and x > 0 else "-")
    display_df["체크 시각"] = display_df["체크 시각"].dt.strftime("%Y-%m-%d %H:%M")
    display_df = display_df.sort_values("체크 시각", ascending=False)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── CSV 다운로드 ──
    csv = display_df.to_csv(index=False, encoding="utf-8-sig")
    kw_name = kw_options[selected_id].split(" (")[0]
    st.download_button(
        "📥 CSV 다운로드",
        data=csv,
        file_name=f"rank_history_{kw_name}_{days}days.csv",
        mime="text/csv",
    )
