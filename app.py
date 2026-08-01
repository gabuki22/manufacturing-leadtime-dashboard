# -*- coding: utf-8 -*-
"""제조 납기·품질 실무 대시보드 — 내 현장 문제를 배운 기법으로 푼다.

강의 실습(CS)은 걷어낸 실무 전용. 각 기법에 대기업 검증 근거 배지를 달았다.
탭: 납기 진단 / 공정별 계획서 / 수주 납기 진단 / 품질·불량 분석 / 리포트
데이터 전부 가공(합성) · BigQuery 원천 → 스냅샷 파이프라인(make_snapshot.py).
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots

import reports

# 디자이너 — Tufte 데이터-잉크(Decluttering): 투명 배경(다크에 녹아듦)·x격자 제거·밝은 텍스트
pio.templates["clean"] = go.layout.Template(layout=dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(size=14, color="#D8DEE6"),
    xaxis=dict(showgrid=False, showline=True, linecolor="#3A4553", ticks="outside", ticklen=4, tickcolor="#3A4553"),
    yaxis=dict(showgrid=True, gridcolor="#232D3B", zeroline=False, showline=False),
    title=dict(font=dict(size=16, color="#E6EAF0")),
    legend=dict(font=dict(color="#D8DEE6")),
    colorway=["#5AA6D8", "#F06A7E", "#5FB86A", "#F5A85B", "#A98FD0", "#9AA5B4"],
))
pio.templates.default = "clean"

DATA = Path(__file__).parent / "data"
PROCS = ["사출", "지그삽입", "도장", "레이저", "인쇄", "출하검사"]
STATUS_COLOR = {"오늘 진행": "#2e7d32", "부분 진행": "#f9a825",
                "앞공정 미완료 대기": "#c62828", "여유": "#9e9e9e"}
STATUS_ORDER = ["오늘 진행", "부분 진행", "앞공정 미완료 대기", "여유"]

st.set_page_config(page_title="제조 납기·품질 실무 대시보드", page_icon="🏭", layout="wide")


@st.cache_data
def _read_csv(path: str, _mtime: float) -> pd.DataFrame:
    """_mtime은 캐시 키 전용 인자다. 파일이 바뀌면 값이 달라져 캐시가 자동 무효화된다."""
    return pd.read_csv(path)


def load(name: str) -> pd.DataFrame:
    """CSV 로더. ⚠️ 파일명만 캐시 키로 쓰면 데이터를 갱신해도 옛 내용이 계속 나온다
    (2026-08-01 실제로 겪음 — 재배포로 코드는 바뀌었는데 CSV는 구버전 표시)."""
    p = DATA / f"{name}.csv"
    return _read_csv(str(p), p.stat().st_mtime)


@st.cache_resource
def _bq_live() -> bool:
    try:
        from google.cloud import bigquery
        bigquery.Client(project="gen-lang-client-0109601387").query(
            "SELECT 1", location="asia-northeast3").result()
        return True
    except Exception:
        return False


def ref_badge(text: str):
    """이 기법을 실제로 쓰는 대기업·기관 근거 배지."""
    st.caption(f"📌 **대기업 검증 근거** · {text}")


# ── 상단 ─────────────────────────────────────────────────────────────
st.title("🏭 제조 납기·품질 실무 대시보드")
st.caption("내 현장 문제(도장 병목·수주 납기·잔업·불량)를 **강의·대기업이 검증한 기법**으로 푼다 · "
           "사출 → 지그삽입 → 도장 → 레이저 → 인쇄 → 출하검사 · **데이터 전부 가공(합성)**")
st.markdown("**작성자 : 이기쁨**  ·  모두의연구소 **데이터기반의사결정 7기**  ·  분석 근거 원본: 볼트 위키 `raw/학습/EDATA7기_이기쁨/`")
_snap_date = (DATA / "_snapshot_date.txt").read_text(encoding="utf-8").strip() if (DATA / "_snapshot_date.txt").exists() else "미기록"
if _bq_live():
    st.caption(f"🟢 **BigQuery 라이브 연결됨** — `make_snapshot.py`로 원천에서 스냅샷 최신화(현 스냅샷 기준 {_snap_date}) · BigQuery(wiki_manufacturing) → 스냅샷 CSV → 대시보드")
else:
    st.caption(f"🟡 **스냅샷 데이터 ({_snap_date} 기준)** — 배포 환경에 BigQuery 인증 정보가 없어 그 시점 데이터로 표시 중 · 인증 없어도 정상 렌더(배포 안전)")
st.divider()

# ── 왼쪽 사이드바 네비게이션 (탭 7개가 가로로 넘쳐 스크롤되던 문제 해소)
PAGES = {
    "var": "⚡ 변동 대응",
    "diag": "🩺 납기 진단",
    "plan": "🗓️ 공정별 계획서",
    "order": "📅 수주 납기 진단",
    "qual": "🔬 품질·불량 분석",
    "equip": "⚙️ 설비 불량",
    "report": "📄 리포트",
}
SUBTITLE = {
    "var": "무엇이 납기를 흔드나",
    "diag": "왜 못 맞추나",
    "plan": "오늘 뭘 하나",
    "order": "애초에 가능한가",
    "qual": "진짜 원인은 무엇인가",
    "equip": "어느 호기를 먼저 점검하나",
    "report": "결론",
}
# 어느 주차에 무엇을 배워서 만든 화면인지 — 강의 진도와 산출물의 대응 관계
WEEK = {
    "var": ("4주차 Day5", "워크플로우 실행 · 변동 요인 분해 · 표본 판단"),
    "diag": ("2주차 Day3~5", "체인 분석(여부→횟수) · TOC 병목 · 컴포넌트 발상"),
    "plan": ("2주차 Day5", "납기 역산 · 유한능력 계획 · 공정 BOM"),
    "order": ("2주차 Day5", "수주 가능성 사전 진단(역산 기반)"),
    "qual": ("3주차 Day2~3", "p-value 유의성 · 심슨의 역설 · 다축 세그멘테이션"),
    "equip": ("4주차 Day4", "가중평균 · 표본 하한선 · 공통원인 vs 특수원인"),
    "report": ("3주차 Day4~5", "BLUF · 피라미드 원칙 · confidence 3단계"),
}
with st.sidebar:
    st.markdown("### 🏭 제조 대시보드")
    st.caption("사출 → 지그삽입 → 도장 → 레이저 → 인쇄 → 출하검사")
    _sel = st.radio("메뉴", list(PAGES.values()), label_visibility="collapsed")
    st.divider()
    _k = [k for k, v in PAGES.items() if v == _sel][0]
    st.caption(f"**{_sel}** — {SUBTITLE[_k]}")
    st.caption(f"🎓 **{WEEK[_k][0]}** 산출물")
    st.caption("데이터 전부 가공(합성) · 작성자 이기쁨")
page = [k for k, v in PAGES.items() if v == _sel][0]

if page == "report":
    st.caption(f"🎓 **{WEEK['report'][0]}** 산출물 · 적용한 기법: {WEEK['report'][1]}")
    reports.render_mfg_report(load)

# ══════════════════════════════════════════════════════════════════════
# 탭1. 납기 진단 — 왜 못 맞추나 (6차트)
# ══════════════════════════════════════════════════════════════════════
if page == "diag":
    st.caption(f"🎓 **{WEEK['diag'][0]}** 산출물 · 적용한 기법: {WEEK['diag'][1]}")
    do, jig_m, inv = load("daily_output"), load("jig_master"), load("inventory")
    lt, dd, ri, pg = load("lot_trace"), load("defect_detail"), load("resource_inventory"), load("paint_grouping")

    lt["리드타임"] = (pd.to_datetime(lt.완제품일) - pd.to_datetime(lt.사출일)).dt.days
    lt["불량횟수"] = lt.자재로트.map(dd.groupby("자재로트").size()).fillna(0)
    lt["구간"] = lt.불량횟수.apply(lambda n: "0회" if n == 0 else ("1회" if n == 1 else "2회 이상"))
    avg_lead = lt.리드타임.mean()
    cap = do.groupby("공정").일생산가능수량.mean().round(0).astype(int).sort_values()

    c1, c2, c3 = st.columns(3)
    c1.metric("평균 완제품 리드타임", f"{avg_lead:.0f}일")
    c2.metric(f"병목 공정 일생산능력 ({cap.index[0]})", f"{int(cap.iloc[0]):,}개/일")
    c3.metric("자재 안전재고 미달", f"{(ri.sort_values('기준일').groupby('자재코드').last().부족여부 == 'Y').mean() * 100:.0f}%")

    st.subheader("① 어느 공정이 우리 속도를 정하는가")
    ref_badge("제약이론(TOC) — 가장 느린 공정 하나가 전체 처리량을 정한다(골드랫 'The Goal')")
    cdf = cap.reset_index(name="일생산능력")
    cdf["구분"] = ["가장 느림" if i == 0 else "여유" for i in range(len(cdf))]
    fig1 = px.bar(cdf, x="공정", y="일생산능력", color="구분", log_y=True, text="일생산능력",
                  color_discrete_map={"가장 느림": "crimson", "여유": "lightslategray"},
                  labels={"일생산능력": "일생산능력 (개/일 · 로그축)"})
    fig1.update_traces(texttemplate="%{text:,}", textposition="outside")
    st.plotly_chart(fig1, width="stretch")

    st.subheader("② 그 공정의 능력은 장부와 실사가 같은가")
    jdf = pd.DataFrame({"기준": ["장부 지그 기준", "실사 지그 기준"],
                        "도장 일캐파": [int(jig_m.도장일캐파_장부.sum()), int(jig_m.도장일캐파_실사.sum())],
                        "지그 수": [int(jig_m.장부지그수.sum()), int(jig_m.실사지그수.sum())]})
    fig2 = px.bar(jdf, x="기준", y="도장 일캐파", color="기준", text="도장 일캐파", hover_data=["지그 수"],
                  color_discrete_map={"장부 지그 기준": "lightslategray", "실사 지그 기준": "crimson"},
                  labels={"도장 일캐파": "도장 일캐파 (개/일)"})
    fig2.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, width="stretch")
    st.caption("실사 캐파가 장부보다 낮다 → 병목의 실제 원인은 설비가 아니라 **지그 관리**일 수 있다(무비용 개선 여지).")

    st.subheader("③ 그 능력을 색상 교체가 얼마나 먹는가")
    pgs = pg.sort_values("생산일자")
    fig3 = go.Figure()
    fig3.add_bar(name="품번 개별 생산", x=pgs.생산일자, y=pgs.개별교체분, marker_color="crimson")
    fig3.add_bar(name="색상 묶음 생산", x=pgs.생산일자, y=pgs.묶음교체분, marker_color="seagreen")
    fig3.update_layout(barmode="group", xaxis_title="생산일자", yaxis_title="도장 색상 교체 손실(분)")
    st.plotly_chart(fig3, width="stretch")

    st.subheader("④ 불량이 반복되면 리드타임이 밀리는가")
    ref_badge("여부→횟수 체인 분석 — 넷플릭스·토스의 퍼널 사고('했나'보다 '반복하나')")
    band = (lt.groupby("구간").agg(로트수=("완제품로트", "size"), 평균리드타임=("리드타임", "mean"))
            .round(0).reindex(["0회", "1회", "2회 이상"]).reset_index())
    band["평균리드타임"] = band.평균리드타임.astype(int)
    fig4 = px.bar(band, x="구간", y="평균리드타임", color="구간", text="평균리드타임", hover_data=["로트수"],
                  color_discrete_map={"0회": "lightslategray", "1회": "lightslategray", "2회 이상": "crimson"},
                  labels={"구간": "그 자재로트에서 불량이 발생한 횟수", "평균리드타임": "사출 → 완제품 리드타임(일)"})
    fig4.add_hline(y=avg_lead, line_dash="dash", line_color="gray", annotation_text=f"전체 평균 {avg_lead:.0f}일")
    fig4.update_layout(showlegend=False)
    st.plotly_chart(fig4, width="stretch")

    st.subheader("⑤ 자재가 발목을 잡는가")
    last = ri.sort_values("기준일").groupby("자재코드").last().reset_index()
    last["재고비율"] = (last.현재고 / last.안전재고 * 100).round(0).astype(int)
    last = last.sort_values("재고비율")
    fig5 = px.bar(last, x="자재코드", y="재고비율", color="부족여부", text="재고비율",
                  hover_data=["자재구분", "현재고", "안전재고"],
                  color_discrete_map={"Y": "crimson", "N": "seagreen"},
                  labels={"재고비율": "안전재고 대비 현재고(%)"})
    fig5.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="안전재고 100%")
    fig5.update_layout(xaxis_tickangle=-45)
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
    fig6.update_traces(texttemplate="%{text:,}", textposition="outside")
    st.plotly_chart(fig6, width="stretch")

# ══════════════════════════════════════════════════════════════════════
# 탭2. 공정별 계획서 — 오늘 뭘 하나
# ══════════════════════════════════════════════════════════════════════
if page == "plan":
    st.caption(f"🎓 **{WEEK['plan'][0]}** 산출물 · 적용한 기법: {WEEK['plan'][1]}")
    plans = load("plan_backward_전체")
    jig = load("plan_공정_지그삽입_로딩배분")
    mat = load("plan_자재소요")
    base_day = plans.기준일.iloc[0]
    st.caption(f"영업 출하납기에서 거꾸로 계산한 공정별 오늘 할 일 · 기준일 **{base_day}** · "
               "오늘 실행량 = **앞 공정 재고 있는 만큼**")

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
    figd.update_layout(legend_title="", barmode="stack")
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

    st.markdown(f"### 🟡 부분 진행 — 앞재고 있는 만큼만 ({(d.상태 == '부분 진행').sum()}건)")
    dp = d[d.상태 == "부분 진행"]
    if len(dp):
        st.dataframe(dp[COLS + ["막힌공정"]].reset_index(drop=True), width="stretch", hide_index=True)
        st.warning(f"이 {len(dp)}건은 앞 공정 재고 부족으로 오늘 {int(dp.금일가능수량.sum()):,}개만 생산, "
                   f"**{int(dp.대기수량.sum()):,}개는 앞공정 대기** — 계획이 있어도 재고가 없으면 못 만든다")
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

    md = mat[mat.공정 == proc]
    if len(md):
        st.divider()
        st.markdown(f"### 📦 {proc} 오늘 자재 소요 — BOM × 금일 생산량")
        agg = (md.groupby(["자재구분", "자재명", "소모구분", "단위"]).소요량.sum().round(1)
               .reset_index().sort_values("소요량", ascending=False))
        st.dataframe(agg.reset_index(drop=True), width="stretch", hide_index=True)
        somo = agg[agg.소모구분 == "소모"]
        if len(somo):
            topm = somo.iloc[0]
            st.info(f"오늘 {proc} 생산에 **{topm.자재구분} {topm.소요량:,}{topm.단위}** 등 소모 — 재고와 대조해 발주 판단")

    if proc == "지그삽입":
        st.divider()
        st.markdown("### 🏭 로딩 배분 — 사내 일캐파 초과분은 사외(협력) 로딩으로")
        jj = jig[jig.로딩구분 != "-"]
        st.dataframe(jj[["제품도번", "고객사", "수주수량", "금일가능수량", "사내로딩", "사외협력로딩", "로딩구분"]]
                     .reset_index(drop=True), width="stretch", hide_index=True)
        st.warning(f"사내 {int(jig.사내로딩.sum()):,}개 처리 후 초과 "
                   f"**{int(jig.사외협력로딩.sum()):,}개**를 사외(협력) 로딩으로 이관")

# ══════════════════════════════════════════════════════════════════════
# 탭3. 수주 납기 진단 — 애초에 가능한가
# ══════════════════════════════════════════════════════════════════════
if page == "order":
    st.caption(f"🎓 **{WEEK['order'][0]}** 산출물 · 적용한 기법: {WEEK['order'][1]}")
    diag = load("plan_수주납기진단")
    st.caption("영업이 확보한 기간(**수주일 → 출하납기**)이 **전 공정 필요 리드타임**보다 짧으면 생산은 시작부터 진다. "
               "접수 시점에 이미 불가능한 납기를 색출한다.")
    ref_badge("리드타임·퍼널 게이트 — 넷플릭스·토스가 전환 이전 단계에서 이탈을 거르는 방식")

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
                       showarrow=False, font=dict(color="#F06A7E", size=13))
    fig.update_traces(marker=dict(size=12, opacity=0.8))
    fig.update_layout(legend_title="")
    st.plotly_chart(fig, width="stretch")

    short = diag[diag.납기판정 == "납기 부족(불가)"]
    st.markdown(f"### 🔴 접수 시점에 이미 불가능한 수주 ({len(short)}건)")
    if len(short):
        DCOLS = ["제품도번", "고객사", "차종", "수주수량", "수주일", "출하납기",
                 "확보기간일", "필요리드타임일", "납기여유일"]
        st.dataframe(short[DCOLS].reset_index(drop=True), width="stretch", hide_index=True)
        st.error(f"이 {len(short)}건은 **수주일부터 계산해도 납기 < 필요 리드타임** — "
                 "접수 단계에서 걸러야 할 건(영업·생산 협의로 납기 재조정)")
    else:
        st.success("접수 시점에 불가능한 수주 없음")

    with st.expander(f"🟡 빠듯한 수주 — 여유 0~2일 ({int(vc.get('빠듯', 0))}건, 변수 생기면 위험)"):
        tight = diag[diag.납기판정 == "빠듯"]
        st.dataframe(tight[["제품도번", "고객사", "수주수량", "수주일", "출하납기",
                            "확보기간일", "필요리드타임일", "납기여유일"]].reset_index(drop=True),
                     width="stretch", hide_index=True)

# ══════════════════════════════════════════════════════════════════════
# 탭4. 품질·불량 분석 — 진짜 원인은 무엇인가 (통계로 오판 방지)
# ══════════════════════════════════════════════════════════════════════
if page == "qual":
    st.caption(f"🎓 **{WEEK['qual'][0]}** 산출물 · 적용한 기법: {WEEK['qual'][1]}")
    st.caption("불량의 진짜 원인을 통계로 가린다 — **사람인가 상황인가**, **고객사인가 색상인가**. "
               "집계 숫자 하나로 갈구지 않고 유의성·층화·세그로 오판을 막는다.")

    st.subheader("① 잔업은 사람 문제인가 상황 문제인가 (유의성 검정)")
    ref_badge("상관 + p-value — 넷플릭스·마이크로소프트(Kohavi)가 A/B 결과를 판정하는 표준")
    ot_def = load("overtime_defect_analysis")
    ot_proc = load("overtime_defect_by_process")
    st.markdown("| 관계 | 통계 판정 |\n|---|---|\n"
                "| 잔업 여부 ↔ 불량률 | z=19.41, **p<0.0001 매우 유의** |\n"
                "| **작업자별** 잔업 ↔ 불량률 | r=−0.10, p=0.60 **무관** |")
    figC = make_subplots(rows=1, cols=2, subplot_titles=("전체 불량률", "공정별 층화(교란변수 점검)"))
    figC.add_bar(x=ot_def.구분, y=ot_def.불량률.round(1), text=ot_def.불량률.round(1),
                 marker_color=["lightslategray", "crimson"], row=1, col=1, showlegend=False)
    for grp, color in [("정상일", "lightslategray"), ("잔업일", "crimson")]:
        subp = ot_proc[ot_proc.구분 == grp]
        figC.add_bar(x=subp.공정, y=subp.불량률.round(1), name=grp, text=subp.불량률.round(1), marker_color=color, row=1, col=2)
    figC.update_traces(textposition="outside")
    figC.update_layout(height=360)
    st.plotly_chart(figC, width="stretch")
    st.error("잔업일 2.7% vs 정상일 2.0%(**p<0.0001**). 도장·레이저 둘 다 잔업일이 높아 공정 구성 탓(교란변수)이 아니다. "
             "작업자별은 무관(p=0.60) → **잔업은 사람이 아니라 상황(잔업 조건) 문제**. 개인 문책은 통계 근거가 없다.")

    st.subheader("② 불량은 고객사가 원인인가 색상이 원인인가 (심슨의 역설)")
    ref_badge("심슨의 역설 — UC버클리 입학 논란(Science)·부킹닷컴 A/B가 겪은 교란변수 함정")
    sp = load("simpson_defect")
    spb = sp.dropna(subset=["black_rate"]).copy()
    figSp = make_subplots(rows=1, cols=2, subplot_titles=("전체 (모든 색상)", "블랙만 층화"))
    so = sp.sort_values("total_rate", ascending=False)
    figSp.add_bar(x=so.customer, y=so.total_rate.round(1), text=so.total_rate.round(1),
                  marker_color=["crimson" if c == so.customer.iloc[0] else "lightslategray" for c in so.customer],
                  row=1, col=1, showlegend=False)
    sb = spb.sort_values("black_rate", ascending=False)
    figSp.add_bar(x=sb.customer, y=sb.black_rate.round(1), text=sb.black_rate.round(1),
                  marker_color=["crimson" if c == sb.customer.iloc[0] else "lightslategray" for c in sb.customer],
                  row=1, col=2, showlegend=False)
    figSp.update_traces(textposition="outside")
    figSp.update_layout(height=360)
    st.plotly_chart(figSp, width="stretch")
    st.error("전체는 **D사 1위(2.1%)** — 하지만 D사는 블랙 100% 주문사. 블랙만 보면 **A사 1위(3.0%)로 역전**. "
             "고객사는 불량의 원인이 아니라 **색상(블랙)의 대리변수** — 조준할 건 'D사 물량'이 아니라 **블랙 도장 조건**.")

    st.subheader("③ 어느 축이 진짜 불량을 가르나 (다축 세그멘테이션)")
    ref_badge("세그멘테이션 — 토스 TUES(2,800만 유저 세그)·불량은 반드시 '률' 기준으로 쪼갠다")
    ma = load("multiaxis_defect")
    figMa = px.bar(ma, x="axis", y="ratio", text="ratio",
                   labels={"axis": "세그 축", "ratio": "변별력 (최고÷최저 불량률, 배)"})
    figMa.update_traces(marker_color=["crimson" if a == "색상" else "lightslategray" for a in ma.axis], textposition="outside")
    figMa.update_layout(height=320)
    st.plotly_chart(figMa, width="stretch")
    st.warning("**색상 축이 변별력 2.2배로 최고**(블랙). 불량 '수량'이 아니라 **'률'로 쪼개니** 물량 착시가 걷힌다 — "
               "PPM 개선은 색상(블랙)부터. 호기라인(1.0배)은 변별력 없음 = 불량 원인 아님.")

if page == "equip":
    st.caption(f"🎓 **{WEEK['equip'][0]}** 산출물 · 적용한 기법: {WEEK['equip'][1]}")
    st.caption("호기별 투입 대비 손실로 **점검 우선순위**를 정한다. 순위표 하나로 끝내지 않고 "
               "**가중평균·표본·공통원인 여부** 세 관문을 통과시킨다 — 셋 중 하나만 빠져도 엉뚱한 설비를 뜯게 된다.")
    st.info("**측정 대상이 품질·불량 탭과 다르다.** 여기는 `투입 대비 손실`(공정 단위)이고, "
            "품질 탭 ③의 '호기라인 변별력 없음'은 `검사에서 판정된 제품 불량`(defect_detail) 기준이다. "
            "서로 다른 질문에 답하는 두 데이터라 결론이 달라도 모순이 아니다. "
            "불량률 정의 = **불량수량 ÷ 투입**(재작업 제외) — 원본이 쓰는 정의와 대조해 확정했다.")

    eq = load("equipment_production")
    st.caption(f"데이터: {eq.월.min()} ~ {eq.월.max()} ({eq.월.nunique()}개월) · "
               f"투입·양품은 기존 작업일보 실제 집계와 **3개월 전부 대조 검증 통과**(30/30) · "
               f"손실의 재작업/불량 분해는 합성")
    tot_in, tot_def = int(eq.투입.sum()), int(eq.불량수량.sum())
    by_m = eq.groupby("월").apply(lambda g: g.불량수량.sum() / g.투입.sum() * 100)
    _rate = lambda d: d.groupby("호기").apply(lambda g: g.불량수량.sum() / g.투입.sum())
    _first = eq.월.min()
    _before, _after = _rate(eq[eq.월 == _first]), _rate(eq[eq.월 != _first])
    _common = _before.index.intersection(_after.index)   # 첫 월에 없는 신규 호기는 비교 대상에서 제외
    worsened, compared = int((_after[_common] > _before[_common]).sum()), len(_common)

    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입 / 불량", f"{tot_in:,}개", f"불량 {tot_def:,}개 ({tot_def/tot_in*100:.2f}%)")
    c2.metric("불량률 추세", f"{by_m.iloc[-1]:.2f}%", f"{by_m.iloc[-1]-by_m.iloc[0]:+.2f}%p (3개월)")
    _share = worsened / compared if compared else 0
    c3.metric("악화된 호기", f"{worsened} / {compared}",
              ("과반이 함께 악화 — 공통 원인 의심" if _share >= 0.7 else
               "일부만 악화 — 개별 설비 쪽" if _share < 0.5 else "절반 안팎 — 판단 보류"),
              delta_color="inverse")

    st.subheader("① 순위를 정하는 방법이 결론을 바꾼다 (가중평균 vs 단순평균)")
    ref_badge("가중평균 — 로트 크기가 다르면 단순 평균이 작은 로트를 과대 반영(제조 통계의 기본)")
    g = eq.groupby(["라인", "호기"]).agg(투입=("투입", "sum"), 불량=("불량수량", "sum"),
                                       개월=("월", "nunique")).reset_index()
    g["가중평균"] = (g.불량 / g.투입 * 100).round(2)
    g["단순평균"] = (eq.groupby(["라인", "호기"]).불량률.mean().values * 100).round(2)
    g = g.sort_values("가중평균", ascending=False)
    worst = g.호기.iloc[0]

    figE = go.Figure()
    figE.add_bar(x=g.호기, y=g.가중평균, name="가중평균 (총불량÷총투입)", text=g.가중평균,
                 marker_color=["crimson" if h == worst else "lightslategray" for h in g.호기])
    figE.add_bar(x=g.호기, y=g.단순평균, name="단순평균 (월별 평균)", text=g.단순평균,
                 marker_color="#5AA6D8", opacity=0.55)
    figE.update_traces(textposition="outside", texttemplate="%{text:.2f}")
    figE.update_layout(barmode="group", height=380, yaxis_title="불량률 (%)",
                       legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(figE, width="stretch")
    st.warning(f"투입량이 최대 **{g.투입.max()/g.투입.min():.0f}배** 차이(가장 큰 호기 {g.투입.max():,} vs 가장 작은 {g.투입.min():,}). "
               "이만큼 벌어지면 단순 평균은 **작은 호기의 값을 과대 반영**해 중위권 순위가 뒤바뀐다. "
               "점검 순번은 **가중평균** 기준으로 읽어야 한다.")

    st.subheader("② 1위를 믿어도 되는가 (표본 확인)")
    ref_badge("표본 크기 판단 — 분모가 작으면 순위가 맞아도 결론을 내리지 않는다(3주차 원칙 재적용)")
    figS = px.scatter(g, x="투입", y="가중평균", text="호기", size="투입", size_max=42,
                      color=g.개월.astype(str), labels={"투입": "총 투입 수량 (개)", "가중평균": "불량률 (%)",
                                                       "color": "관측 개월"})
    figS.update_traces(textposition="top center")
    figS.add_vline(x=g.투입.median() * 0.2, line_dash="dot", line_color="#F5A85B",
                   annotation_text="표본 하한선 (중앙값의 20%)", annotation_position="top")
    figS.update_layout(height=380)
    st.plotly_chart(figS, width="stretch")
    small = g[(g.개월 < g.개월.max()) | (g.투입 < g.투입.median() * 0.2)]
    if len(small):
        names = " · ".join(f"**{r.호기}**(투입 {int(r.투입):,}·{int(r.개월)}개월·{r.가중평균}%)" for _, r in small.iterrows())
        st.error(f"{names} 는 **표본이 부족해 판정 보류**. 왼쪽 아래 점선 왼편은 분모가 작아 몇 건 차이로 순위가 뒤집힌다. "
                 "신규 설비는 초기 안정화 기간에 불량이 높은 것이 정상이라, 이 숫자로 최우선 점검을 결정하면 오판이다.")

    st.subheader("③ 특정 호기 문제인가, 전체가 같이 나빠졌는가")
    ref_badge("공통원인 vs 특수원인 — 슈하트/데밍 관리도의 기본 구분. 공통원인을 개별 설비로 처리하면 개선이 안 된다")
    piv = eq.pivot_table(index="호기", columns="월", values="불량수량", aggfunc="sum") / \
          eq.pivot_table(index="호기", columns="월", values="투입", aggfunc="sum") * 100
    first, last = piv.columns[0], piv.columns[-1]
    piv = piv.sort_values(last, ascending=False)
    figT = go.Figure()
    for h in piv.index:
        vals = piv.loc[h]
        figT.add_scatter(x=list(piv.columns), y=vals, mode="lines+markers", name=h,
                         line=dict(width=3 if h in small.호기.values or h == worst else 1.5,
                                   color="crimson" if h == worst else None))
    figT.update_layout(height=400, yaxis_title="불량률 (%)", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(figT, width="stretch")
    if _share >= 0.7:
        st.error(f"**{worsened}/{compared} 호기가 함께 악화**됐다({by_m.iloc[0]:.2f}% → {by_m.iloc[-1]:.2f}%). "
                 "특정 설비 고장이라면 한둘만 튀어야 하는데 대부분이 같이 올랐다 — **자재 로트·환경·작업조건 같은 공통 원인**을 먼저 의심해야 한다. "
                 "순위표만 보고 1위 설비를 뜯으면, 뜯고 나서도 나머지 호기의 불량률은 그대로다.")
    else:
        st.warning(f"**{worsened}/{compared} 호기만 악화**됐다({by_m.iloc[0]:.2f}% → {by_m.iloc[-1]:.2f}%). "
                   "과반이 함께 움직이지 않았으므로 **공통 원인이라고 말할 근거는 약하다** — 개별 설비 쪽을 먼저 본다. "
                   "다만 이 판정은 3개월(월 3점)에 기댄 것이라 **추세라고 부르기엔 짧다**. 표본을 더 쌓은 뒤 재판정해야 한다.")

    st.success(f"**점검 우선순위** ① {'공통 원인 조사' if _share >= 0.7 else '개별 설비 점검'}(악화 {worsened}/{compared}대) — *confidence 낮음~중간, 월 3점이라 추세 판정엔 부족* "
               f"② {' · '.join(g[~g.호기.isin(small.호기)].호기.head(2).tolist())} — 공통 상승분을 빼도 가장 큼 "
               f"③ {' · '.join(small.호기.tolist()) if len(small) else '없음'} — 관측만, 판정 보류")

# ══════════════════════════════════════════════════════════════════════
# 탭0. 변동 대응 — 나의 분석 워크플로우 Define에 직접 답하는 페이지
# ══════════════════════════════════════════════════════════════════════
if page == "var":
    st.caption(f"🎓 **{WEEK['var'][0]}** 산출물 · 적용한 기법: {WEEK['var'][1]}")
    st.markdown("### ❓ 우리 납기를 실제로 흔드는 변동은 셋 중 무엇이고, 각각에 대응할 시간이 얼마나 남아 있는가?")
    st.caption("계획을 흔드는 변수 셋 — **A 발주 변동**(주 단위 접수량이 크게 출렁) · **B 리드타임 변동**(자재·설비 문제 시 길어짐) · "
               "**C 계획 외 삽입**(품질 대체품·개발품이 계획과 무관하게 끼어듦). "
               "셋 중 무엇부터 손볼지 정하는 것이 이 페이지의 목적이다 — 셋 다 동시에 할 수 없다.")

    imp, fcq = load("variation_impact"), load("variation_forecast")
    ords, insr = load("variation_orders"), load("variation_insertions")

    st.warning("⚠️ **데이터 한계를 먼저 밝힌다.** 이 페이지는 **합성 데이터** 기준이고, "
               "생산 리드타임 중앙값이 **11일**로 나온다 — 현장 실측 **3~5일**과 크게 다르다. "
               "합성 시 리드타임 파라미터를 실제에 맞추지 않은 결과이지 발견이 아니다. "
               "**변동 간 상대 크기 비교**는 유효하나, **절대 일수는 실데이터로 재계산해야 한다.**")

    c1, c2, c3 = st.columns(3)
    top = imp.sort_values("영향일수", ascending=False).iloc[0]
    c1.metric("가장 큰 변동 요인", top.변동.split()[0] + " " + top.변동.split()[1],
              f"{top.영향일수:.1f}일 영향", delta_color="inverse")
    c2.metric("세 변동 합계", f"{imp.영향일수.sum():.1f}일", "납기를 갉아먹는 총량", delta_color="inverse")
    c3.metric("착수 시점 여유(중앙값)", f"{ords.여유일.median():.0f}일", f"납기 초과율 {ords.납기초과.mean()*100:.1f}%")

    st.subheader("① 셋 중 무엇이 가장 크게 흔드는가")
    ref_badge("영향도 우선순위 — 원인이 여럿일 때 크기 순으로 조준한다(파레토 원칙의 기본형)")
    imps = imp.sort_values("영향일수")
    figV = px.bar(imps, x="영향일수", y="변동", orientation="h", text="영향일수",
                  color="변동", color_discrete_map={v: ("crimson" if v == top.변동 else "lightslategray")
                                                    for v in imp.변동},
                  hover_data=["산출근거", "표본", "confidence"],
                  labels={"영향일수": "납기를 갉아먹는 일수 (일)", "변동": ""})
    figV.update_traces(texttemplate="%{text:.1f}일", textposition="outside")
    figV.update_layout(showlegend=False, height=300)
    st.plotly_chart(figV, width="stretch")
    st.dataframe(imp[["변동", "영향일수", "산출근거", "표본", "confidence"]],
                 width="stretch", hide_index=True)
    st.error(f"**A(발주 변동)가 {top.영향일수:.1f}일로 가장 크다** — B의 {imp[imp.변동.str.startswith('B')].영향일수.iloc[0]:.1f}일, "
             f"C의 {imp[imp.변동.str.startswith('C')].영향일수.iloc[0]:.1f}일보다 크다. "
             "**설비·자재보다 '무엇을 언제 만들지가 흔들리는 것'이 더 큰 문제**라는 뜻이다. "
             "다만 셋은 그레인이 달라(수주/수주/삽입건) 같은 축에 놓은 **근사 비교**이며, 인과가 아니라 크기 비교용이다.")

    st.subheader("② A — 발주 예보가 흔들리면 착수가 늦어진다")
    ref_badge("층화 비교 — 변동성 3분위로 나눠 다른 조건을 고르게 만든 뒤 비교(교란변수 통제)")
    figA = make_subplots(rows=1, cols=2, subplot_titles=("착수 리드타임 (접수→착수)", "착수 시점 남은 여유"))
    figA.add_bar(x=fcq.변동성구간, y=fcq.착수LT.round(1), text=fcq.착수LT.round(1),
                 marker_color=["lightslategray", "lightslategray", "crimson"], row=1, col=1, showlegend=False)
    figA.add_bar(x=fcq.변동성구간, y=fcq.여유일, text=fcq.여유일,
                 marker_color=["seagreen", "lightslategray", "crimson"], row=1, col=2, showlegend=False)
    figA.update_traces(textposition="outside")
    figA.update_layout(height=330)
    st.plotly_chart(figA, width="stretch")
    st.error(f"예보가 **불안정한 도번은 착수가 {fcq.착수LT.iloc[-1]:.1f}일**로 안정군({fcq.착수LT.iloc[0]:.1f}일)의 "
             f"**{fcq.착수LT.iloc[-1]/fcq.착수LT.iloc[0]:.1f}배**. 남은 여유도 {fcq.여유일.iloc[0]:.0f}일 → {fcq.여유일.iloc[-1]:.0f}일로 줄고, "
             f"납기 초과율은 0% → {fcq.납기초과율.iloc[-1]*100:.0f}%로 오른다. "
             "**설비를 늘려도 이 지연은 안 줄어든다 — 언제 만들지 정해지지 않아 못 시작한 시간이기 때문이다.**")

    st.subheader("③ C — 무엇이 끼어들어 며칠을 밀어내는가")
    ref_badge("사건 기록 — 끼어든 순간을 남기지 않으면 '왜 늦었나'를 나중에 설명할 수 없다(4주D1 상태 vs 사건)")
    kind = (insr.groupby("삽입구분").agg(건수=("밀림일수", "size"), 평균밀림=("밀림일수", "mean"),
                                       총밀림일=("밀림일수", "sum")).reset_index()
            .sort_values("평균밀림", ascending=False))
    figC = px.bar(kind, x="삽입구분", y="평균밀림", text="평균밀림", hover_data=["건수", "총밀림일"],
                  color="삽입구분",
                  color_discrete_map={k: ("crimson" if k == kind.삽입구분.iloc[0] else "lightslategray")
                                      for k in kind.삽입구분},
                  labels={"평균밀림": "삽입 1건당 평균 밀림 일수 (일)"})
    figC.update_traces(texttemplate="%{text:.2f}일", textposition="outside")
    figC.update_layout(showlegend=False, height=320)
    st.plotly_chart(figC, width="stretch")
    st.info(f"**{kind.삽입구분.iloc[0]}가 1건당 {kind.평균밀림.iloc[0]:.2f}일**로 가장 크게 민다. "
            f"다만 건수는 **{kind.sort_values('총밀림일', ascending=False).삽입구분.iloc[0]}**가 많아 "
            f"총 밀림일은 {kind.sort_values('총밀림일', ascending=False).총밀림일.iloc[0]}일로 더 크다 — "
            "**1건당 충격이 큰 것과 전체 손실이 큰 것은 다르다.** 줄일 대상은 후자, 예방할 대상은 전자.")
    st.caption(f"※ 삽입 이력은 {len(insr)}건으로 표본이 작다(confidence 낮음). "
               "또 도번 정보가 없어 **월 단위로만** 다른 데이터와 결합된다 — 특정 수주가 이 삽입 때문에 밀렸는지는 알 수 없다.")

    st.success("**결론** ① 먼저 손볼 것은 **A(발주 예보 안정화)** — 영향이 가장 크고, 설비 증설로는 줄지 않는다 "
               "② B는 리드타임 자체보다 **P90 꼬리**(악화 시 추가 5일)를 줄이는 문제 "
               "③ C는 총량은 작지만 **기록이 없으면 원인 규명이 불가능**하므로 수집부터 시작 "
               "· *confidence: A 중간 / B 중간 / C 낮음 — 절대 일수는 실데이터 재계산 필요*")
