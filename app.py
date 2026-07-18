# -*- coding: utf-8 -*-
"""제조 납기 관리 대시보드 — 진단 + 계획서 (탭 통합).

탭1 납기 진단  : "우리는 왜 납기를 못 맞추는가" 6개 차트(리드타임·병목·불량체인).
탭2 공정 계획서: 영업 출하납기 역산 → 공정별 '오늘 진행 / 앞공정 미완료 대기 / 여유'.

데이터기반의사결정 7기 · 2주차 프로젝트 · 이기쁨 · 데이터 전부 가공(합성)
로컬 실행:  py -m streamlit run app.py
배포:       GitHub push → Streamlit Community Cloud (Main file path = app.py)
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).parent / "data"
PROCS = ["사출", "지그삽입", "도장", "레이저", "인쇄", "출하검사"]
STATUS_COLOR = {"오늘 진행": "#2e7d32", "부분 진행": "#f9a825",
                "앞공정 미완료 대기": "#c62828", "여유": "#9e9e9e"}
STATUS_ORDER = ["오늘 진행", "부분 진행", "앞공정 미완료 대기", "여유"]

st.set_page_config(page_title="제조 납기 관리 대시보드", page_icon="🏭", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


# ── 상단: 제목 · 설명 · 작성자(강사 확인용) ───────────────────────────
st.title("🏭 제조 납기 관리 대시보드")
st.caption("영업 출하납기 기준 — **왜 못 맞추나(진단)** 와 **오늘 뭘 해야 하나(계획서)** 를 한 곳에서 · "
           "사출 → 지그삽입 → 도장 → 레이저 → 인쇄 → 출하검사 · **데이터 전부 가공(합성)**")
st.markdown("**작성자 : 이기쁨**  ·  모두의연구소 **데이터기반의사결정 7기**  ·  2026년 7월  "
            "·  분석 근거 원본: 볼트 위키 `raw/학습/EDATA7기_이기쁨/`")
st.divider()

tab_diag, tab_plan, tab_order = st.tabs(
    ["🩺 납기 진단 — 왜 못 맞추나", "🗓️ 공정별 계획서 — 오늘 뭘 하나", "📅 수주 납기 진단 — 애초에 가능한가"])

# ══════════════════════════════════════════════════════════════════════
# 탭1. 납기 진단 — 왜 못 맞추나 (6개 차트)
# ══════════════════════════════════════════════════════════════════════
with tab_diag:
    do, jig_m, inv = load("daily_output"), load("jig_master"), load("inventory")
    lt, dd, ri, pg = load("lot_trace"), load("defect_detail"), load("resource_inventory"), load("paint_grouping")

    lt["리드타임"] = (pd.to_datetime(lt.완제품일) - pd.to_datetime(lt.사출일)).dt.days
    lt["불량횟수"] = lt.자재로트.map(dd.groupby("자재로트").size()).fillna(0)
    lt["구간"] = lt.불량횟수.apply(lambda n: "0회" if n == 0 else ("1회" if n == 1 else "2회 이상"))
    avg_lead = lt.리드타임.mean()
    cap = do.groupby("공정").일생산가능수량.mean().sort_values()

    c1, c2, c3 = st.columns(3)
    c1.metric("평균 완제품 리드타임", f"{avg_lead:.1f}일")
    c2.metric(f"병목 공정 일생산능력 ({cap.index[0]})", f"{int(cap.iloc[0]):,}개/일")
    c3.metric("자재 안전재고 미달", f"{(ri.sort_values('기준일').groupby('자재코드').last().부족여부 == 'Y').mean() * 100:.0f}%")

    st.subheader("① 어느 공정이 우리 속도를 정하는가")
    cdf = cap.reset_index(name="일생산능력")
    cdf["구분"] = ["가장 느림" if i == 0 else "여유" for i in range(len(cdf))]
    fig1 = px.bar(cdf, x="공정", y="일생산능력", color="구분", log_y=True, text="일생산능력",
                  color_discrete_map={"가장 느림": "crimson", "여유": "lightslategray"},
                  labels={"일생산능력": "일생산능력 (개/일 · 로그축)"})
    fig1.update_layout(font=dict(size=13))
    st.plotly_chart(fig1, width="stretch")

    st.subheader("② 그 공정의 능력은 장부와 실사가 같은가")
    jdf = pd.DataFrame({"기준": ["장부 지그 기준", "실사 지그 기준"],
                        "도장 일캐파": [int(jig_m.도장일캐파_장부.sum()), int(jig_m.도장일캐파_실사.sum())],
                        "지그 수": [int(jig_m.장부지그수.sum()), int(jig_m.실사지그수.sum())]})
    fig2 = px.bar(jdf, x="기준", y="도장 일캐파", color="기준", text="도장 일캐파", hover_data=["지그 수"],
                  color_discrete_map={"장부 지그 기준": "lightslategray", "실사 지그 기준": "crimson"},
                  labels={"도장 일캐파": "도장 일캐파 (개/일)"})
    fig2.update_layout(font=dict(size=13), showlegend=False)
    st.plotly_chart(fig2, width="stretch")

    st.subheader("③ 그 능력을 색상 교체가 얼마나 먹는가")
    pgs = pg.sort_values("생산일자")
    fig3 = go.Figure()
    fig3.add_bar(name="품번 개별 생산", x=pgs.생산일자, y=pgs.개별교체분, marker_color="crimson")
    fig3.add_bar(name="색상 묶음 생산", x=pgs.생산일자, y=pgs.묶음교체분, marker_color="seagreen")
    fig3.update_layout(barmode="group", font=dict(size=13), xaxis_title="생산일자",
                       yaxis_title="도장 색상 교체 손실(분)")
    st.plotly_chart(fig3, width="stretch")

    st.subheader("④ 불량이 반복되면 리드타임이 밀리는가")
    band = (lt.groupby("구간").agg(로트수=("완제품로트", "size"), 평균리드타임=("리드타임", "mean"))
            .round(2).reindex(["0회", "1회", "2회 이상"]).reset_index())
    fig4 = px.bar(band, x="구간", y="평균리드타임", color="구간", text="평균리드타임", hover_data=["로트수"],
                  color_discrete_map={"0회": "lightslategray", "1회": "lightslategray", "2회 이상": "crimson"},
                  labels={"구간": "그 자재로트에서 불량이 발생한 횟수", "평균리드타임": "사출 → 완제품 리드타임(일)"})
    fig4.add_hline(y=avg_lead, line_dash="dash", line_color="gray", annotation_text=f"전체 평균 {avg_lead:.1f}일")
    fig4.update_layout(font=dict(size=13), showlegend=False)
    st.plotly_chart(fig4, width="stretch")

    st.subheader("⑤ 자재가 발목을 잡는가")
    last = ri.sort_values("기준일").groupby("자재코드").last().reset_index()
    last["재고비율"] = (last.현재고 / last.안전재고 * 100).round(1)
    last = last.sort_values("재고비율")
    fig5 = px.bar(last, x="자재코드", y="재고비율", color="부족여부", text="재고비율",
                  hover_data=["자재구분", "현재고", "안전재고"],
                  color_discrete_map={"Y": "crimson", "N": "seagreen"},
                  labels={"재고비율": "안전재고 대비 현재고(%)"})
    fig5.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="안전재고 100%")
    fig5.update_layout(font=dict(size=12), xaxis_tickangle=-45)
    st.plotly_chart(fig5, width="stretch")

    st.subheader("⑥ 재고는 어느 공정 앞에 쌓여 있는가")
    stages = [c for c in inv.columns if c.startswith("재고_")]
    sdf = pd.DataFrame({"단계": [s.replace("재고_", "") for s in stages],
                        "재고수량": [int(inv[s].sum()) for s in stages]})
    top = sdf.재고수량.idxmax()
    sdf["구분"] = ["가장 많이 쌓임" if i == top else "일반" for i in range(len(sdf))]
    fig6 = px.bar(sdf, x="단계", y="재고수량", color="구분", text="재고수량",
                  color_discrete_map={"가장 많이 쌓임": "crimson", "일반": "lightslategray"},
                  category_orders={"단계": [s.replace("재고_", "") for s in stages]},
                  labels={"단계": "재고 파이프라인 9단계 (공정 순서)", "재고수량": "누적 재고 수량"})
    fig6.update_layout(font=dict(size=13))
    st.plotly_chart(fig6, width="stretch")

# ══════════════════════════════════════════════════════════════════════
# 탭2. 공정별 계획서 — 오늘 뭘 하나 (납기 역산)
# ══════════════════════════════════════════════════════════════════════
with tab_plan:
    plans = load("plan_backward_전체")
    jig = load("plan_공정_지그삽입_로딩배분")
    mat = load("plan_자재소요")
    base_day = plans.기준일.iloc[0]
    st.caption(f"영업 출하납기에서 거꾸로 계산한 공정별 오늘 할 일 · 기준일 **{base_day}** · "
               "오늘 실행량 = **앞 공정 재고 있는 만큼**(재고는 여러 공정에 나뉘어 있음)")

    run = plans[plans.상태.isin(["오늘 진행", "부분 진행"])]
    part = plans[plans.상태 == "부분 진행"]
    wait = plans[plans.상태 == "앞공정 미완료 대기"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("오늘 생산 착수", f"{len(run)}건")
    k2.metric("금일 총 생산량", f"{int(run.금일가능수량.sum()):,}개")
    k3.metric("부분 진행(앞재고 부족)", f"{len(part)}건", delta="일부만", delta_color="inverse")
    k4.metric("앞공정 미완료 대기", f"{len(wait)}건", delta="병목", delta_color="inverse")

    st.subheader("공정별 상태 분포 — 어디에 일이 몰려 있나")
    dist = plans.groupby(["공정", "상태"]).size().reset_index(name="건수")
    figd = px.bar(dist, x="공정", y="건수", color="상태", text="건수",
                  category_orders={"공정": PROCS, "상태": STATUS_ORDER}, color_discrete_map=STATUS_COLOR)
    figd.update_layout(font=dict(size=13), legend_title="", barmode="stack")
    st.plotly_chart(figd, width="stretch")

    st.divider()
    proc = st.radio("공정 선택", PROCS, horizontal=True)
    d = plans[plans.공정 == proc]
    COLS = ["제품도번", "고객사", "차종", "색상", "수주수량", "수주일", "출하납기", "착수목표일",
            "필요량", "앞공정재고", "일생산능력", "금일가능수량", "대기수량"]

    st.markdown(f"### 🟢 오늘 진행 — 앞재고로 전량 가능 ({(d.상태 == '오늘 진행').sum()}건)")
    dt = d[d.상태 == "오늘 진행"]
    if len(dt):
        st.dataframe(dt[COLS].reset_index(drop=True), width="stretch", hide_index=True)
    else:
        st.info("앞재고로 전량 가능한 건이 없습니다.")

    st.markdown(f"### 🟡 부분 진행 — 앞재고 있는 만큼만, 나머지 대기 ({(d.상태 == '부분 진행').sum()}건)")
    dp = d[d.상태 == "부분 진행"]
    if len(dp):
        st.dataframe(dp[COLS + ["막힌공정"]].reset_index(drop=True), width="stretch", hide_index=True)
        st.warning(f"이 {len(dp)}건은 **앞 공정 재고가 필요량보다 적어** 오늘은 {int(dp.금일가능수량.sum()):,}개만 "
                   f"생산하고 **{int(dp.대기수량.sum()):,}개는 앞공정 대기** — 계획이 있어도 재고가 없으면 못 만든다")
    else:
        st.caption("부분 진행 없음.")

    st.markdown(f"### 🔴 앞공정 미완료 대기 — 앞재고 0 ({(d.상태 == '앞공정 미완료 대기').sum()}건)")
    dw = d[d.상태 == "앞공정 미완료 대기"]
    if len(dw):
        st.dataframe(dw[COLS + ["막힌공정"]].reset_index(drop=True), width="stretch", hide_index=True)
        blk = " · ".join(f"**{k}** {v}건" for k, v in dw.막힌공정.value_counts().items())
        st.error(f"막힌 공정: {blk} — 이 공정들이 끝나야 착수 가능")
    else:
        st.caption("앞공정 미완료 대기 없음.")

    with st.expander(f"⚪ 여유 — 역산 착수일이 아직 미래 ({(d.상태 == '여유').sum()}건)"):
        dv = d[d.상태 == "여유"].sort_values("착수목표일")
        st.dataframe(dv[COLS + ["여유일"]].reset_index(drop=True), width="stretch", hide_index=True)

    # 선택 공정의 오늘 자재 소요 (BOM × 오늘 생산량)
    md = mat[mat.공정 == proc]
    if len(md):
        st.divider()
        st.markdown(f"### 📦 {proc} 오늘 자재 소요 — BOM × 금일 생산량")
        agg = (md.groupby(["자재구분", "자재명", "소모구분", "단위"]).소요량.sum().round(1)
               .reset_index().sort_values("소요량", ascending=False))
        st.dataframe(agg.reset_index(drop=True), width="stretch", hide_index=True)
        somo = agg[agg.소모구분 == "소모"]
        if len(somo):
            top = somo.iloc[0]
            st.info(f"오늘 {proc} 생산에 **{top.자재구분} {top.소요량:,}{top.단위}** 등 소모 — 자재 재고와 대조해 발주 판단")

    if proc == "지그삽입":
        st.divider()
        st.markdown("### 🏭 로딩 배분 — 사내 일캐파 초과분은 사외(협력) 로딩으로")
        jj = jig[jig.로딩구분 != "-"]
        st.dataframe(jj[["제품도번", "고객사", "수주수량", "금일가능수량", "사내로딩", "사외협력로딩", "로딩구분"]]
                     .reset_index(drop=True), width="stretch", hide_index=True)
        st.warning(f"사내 {int(jig.사내로딩.sum()):,}개 처리 후 초과 "
                   f"**{int(jig.사외협력로딩.sum()):,}개**를 사외(협력) 로딩으로 이관")

# ══════════════════════════════════════════════════════════════════════
# 탭3. 수주 납기 진단 — 애초에 가능한 납기였나
# ══════════════════════════════════════════════════════════════════════
with tab_order:
    diag = load("plan_수주납기진단")
    st.caption("영업이 확보한 기간(**수주일 → 출하납기**)이 **전 공정 필요 리드타임**보다 짧으면, "
               "생산은 시작부터 진다. 수주 접수 시점에 이미 불가능한 납기를 색출한다.")

    vc = diag.납기판정.value_counts()
    o1, o2, o3 = st.columns(3)
    o1.metric("🟢 여유 (리드타임+3일↑)", f"{int(vc.get('여유', 0))}건")
    o2.metric("🟡 빠듯 (여유 0~2일)", f"{int(vc.get('빠듯', 0))}건")
    o3.metric("🔴 납기 부족(불가)", f"{int(vc.get('납기 부족(불가)', 0))}건", delta="수주 오류", delta_color="inverse")

    st.subheader("확보기간 vs 필요 리드타임 — 대각선 위쪽 = 애초에 부족")
    mx = int(max(diag.확보기간일.max(), diag.필요리드타임일.max())) + 1
    fig = px.scatter(diag, x="확보기간일", y="필요리드타임일", color="납기판정",
                     hover_data=["제품도번", "고객사", "수주수량", "수주일", "출하납기", "납기여유일"],
                     color_discrete_map={"여유": "#2e7d32", "빠듯": "#f9a825", "납기 부족(불가)": "#c62828"},
                     labels={"확보기간일": "확보기간(수주일→납기, 일)", "필요리드타임일": "전 공정 필요 리드타임(일)"})
    fig.add_shape(type="line", x0=0, y0=0, x1=mx, y1=mx, line=dict(dash="dash", color="gray"))
    fig.add_annotation(x=mx * 0.32, y=mx * 0.9, text="이 선 위 = 필요 > 확보 = 납기 부족",
                       showarrow=False, font=dict(color="#c62828", size=13))
    fig.update_traces(marker=dict(size=12, opacity=0.75))
    fig.update_layout(font=dict(size=13), legend_title="")
    st.plotly_chart(fig, width="stretch")

    short = diag[diag.납기판정 == "납기 부족(불가)"]
    st.markdown(f"### 🔴 접수 시점에 이미 불가능한 수주 ({len(short)}건)")
    if len(short):
        DCOLS = ["제품도번", "고객사", "차종", "수주수량", "수주일", "출하납기",
                 "확보기간일", "필요리드타임일", "납기여유일"]
        st.dataframe(short[DCOLS].reset_index(drop=True), width="stretch", hide_index=True)
        st.error(f"이 {len(short)}건은 **수주일부터 계산해도 납기 < 필요 리드타임** — "
                 "영업·생산 협의로 납기 재조정하거나, 접수 단계에서 걸러야 할 건")
    else:
        st.success("접수 시점에 불가능한 수주 없음 — 모든 납기가 리드타임을 확보")

    with st.expander(f"🟡 빠듯한 수주 — 여유 0~2일 ({int(vc.get('빠듯', 0))}건, 변수 생기면 위험)"):
        tight = diag[diag.납기판정 == "빠듯"]
        st.dataframe(tight[["제품도번", "고객사", "수주수량", "수주일", "출하납기",
                            "확보기간일", "필요리드타임일", "납기여유일"]].reset_index(drop=True),
                     width="stretch", hide_index=True)
