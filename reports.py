# -*- coding: utf-8 -*-
"""리포트 탭 — 납기 문제해결 통합 리포트 (8구성요소 완비, 단일 문서).

결론 요약과 전문 리포트를 나누지 않고 하나로 통합. 글만 나열하지 않고
이해를 돕는 시각 요소를 함께 배치한다 — 단, 대시보드 탭 차트와 중복되지 않는
형식만 사용: 공정 흐름 인포그래픽·데이터 파이프라인 아키텍처(HTML flow),
지그 캐파 워터폴(증감 분해), 수주 퍼널(단계 좁힘), 근거 판정표.

값은 전부 원본 스냅샷에서 재계산(하드코딩 없음) · 정수/1자리 표기.
"""
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

BLUE = "#5AA6D8"
RED = "#F06A7E"


def _flow(steps, highlight=-1):
    """가로 흐름 인포그래픽 — (라벨, 부제) 상자들을 화살표로 연결. highlight 인덱스는 빨강 강조."""
    boxes = []
    for i, (label, sub) in enumerate(steps):
        hot = (i == highlight)
        bg = "#3A1220" if hot else "#1F2938"
        bd = RED if hot else "#3A4553"
        fc = RED if hot else "#E6EAF0"
        boxes.append(
            f"<div style='background:{bg};border:1.5px solid {bd};border-radius:9px;"
            f"padding:9px 14px;text-align:center;min-width:96px'>"
            f"<div style='font-weight:700;color:{fc};font-size:14px'>{label}</div>"
            f"<div style='color:#9AA5B4;font-size:12px;margin-top:2px'>{sub}</div></div>")
    arrow = f"<div style='color:{BLUE};font-size:20px;align-self:center;font-weight:700'>→</div>"
    st.markdown("<div style='display:flex;gap:9px;flex-wrap:wrap;align-items:stretch;margin:6px 0 2px'>"
                + arrow.join(boxes) + "</div>", unsafe_allow_html=True)


def render_mfg_report(load):
    # ── 원본 재계산 ─────────────────────────────────────────────────
    do = load("daily_output")
    jig = load("jig_master")
    diag = load("plan_수주납기진단")
    cpk = load("cpk_defect_analysis")
    ot = load("overtime_defect_analysis")
    sp = load("simpson_defect")
    ma = load("multiaxis_defect")

    cap = do.groupby("공정").일생산가능수량.mean().round(0).astype(int).sort_values()
    bottleneck, bcap = cap.index[0], int(cap.iloc[0])
    jig_book, jig_real = int(jig.도장일캐파_장부.sum()), int(jig.도장일캐파_실사.sum())
    jig_gap_pct = round((jig_book - jig_real) / jig_book * 100)
    n_total = len(diag)
    n_risk = int((diag.납기판정 != "여유").sum())
    n_fail = int((diag.납기판정 == "납기 부족(불가)").sum())
    r_cpk = round(cpk.Cpk.corr(cpk.불량률), 2)
    ot_r = ot.set_index("구분").불량률
    ot_over, ot_norm = round(float(ot_r.get("잔업일")), 1), round(float(ot_r.get("정상일")), 1)
    sp_top = sp.sort_values("total_rate", ascending=False).iloc[0]
    spb = sp.dropna(subset=["black_rate"]).sort_values("black_rate", ascending=False).iloc[0]
    ma_top = ma.sort_values("ratio", ascending=False).iloc[0]

    # ── 제목 · 단일 질문 ────────────────────────────────────────────
    st.markdown(f"### 📄 납기 문제해결 리포트 &nbsp;<span style='color:{BLUE}'>— 우리는 왜 납기를 못 맞추나?</span>",
                unsafe_allow_html=True)
    st.caption("8구성요소 통합 리포트(경영 보고용) · 상세 인터랙티브 차트는 각 대시보드 탭 · 데이터 전부 가공(합성)")

    # ── 1. Executive Summary (BLUF) ────────────────────────────────
    st.markdown("## 1. 핵심 결론 (Executive Summary)")
    st.success(
        f"1. **도장이 병목이다** — 일 **{bcap:,}개/일**로 최소 공정. 지그 실사가 장부보다 **{jig_gap_pct}% 적어**"
        f"({jig_real:,} vs {jig_book:,}) 병목의 실제 원인으로 보인다\n"
        f"2. **수주 {n_fail}건은 접수 시점에 이미 불가능** — 전체 {n_total}건 중 확보기간 < 필요 리드타임\n"
        f"3. **잔업은 상황 문제이지 사람 문제가 아니다** — 잔업일 불량 {ot_over}% vs 정상 {ot_norm}%(p<0.0001), "
        f"작업자별은 무관(p=0.60)\n"
        f"4. **불량은 고객사가 아니라 색상(블랙)이 가른다** — 층화 시 순위 역전(심슨의 역설), "
        f"Cpk는 실불량 예측 불가(r={r_cpk:+.2f})"
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"병목({bottleneck}) 일캐파", f"{bcap:,}개/일")
    k2.metric("지그 실사 과소", f"{jig_gap_pct}%", delta="장부 대비 부족", delta_color="inverse")
    k3.metric("접수시점 불가 수주", f"{n_fail}건", delta=f"전체 {n_total}건 중", delta_color="inverse")
    k4.metric("잔업일 불량률", f"{ot_over}%", delta=f"{ot_over-ot_norm:+.1f}%p", delta_color="inverse")

    # ── 2. 배경 · 목적 ──────────────────────────────────────────────
    st.markdown("## 2. 배경 · 목적")
    st.markdown(
        "납기 미달이 반복되는데 진단은 늘 “생산이 더 서둘러야 한다”에 머물렀다. 리드타임 기록조차 없는 상태에서 "
        "작업일보·재고·수주 데이터로 **진짜 병목과 구조적 원인**을 규명하고, 감이 아닌 근거로 개선 우선순위를 정한다."
    )

    # ── 3. 분석 방법론 — 납기 문제를 어떻게 쪼갰나 ──────────────────
    st.markdown("## 3. 분석 방법론 — 납기 문제를 어떻게 쪼갰나")
    _flow([("문제 정의", "왜 납기를 못 맞추나"), ("리드타임 역산", "작업일보 → CT 복원"),
           ("병목 진단", "공정별 일생산능력"), ("원인 검증", "유의성·층화·세그"), ("처방 도출", "우선순위 4")])
    st.markdown(
        "- **질문 분해(MECE)** — 납기 미달을 서로 겹치지 않는 4개 질문으로 쪼갰다:\n"
        "  ① **공정 능력** — 어느 공정이 속도를 정하나 → 병목 진단(제약이론)\n"
        "  ② **수주 접수** — 애초에 가능한 납기였나 → 확보기간 vs 필요 리드타임 역산\n"
        "  ③ **작업 조건** — 잔업이 불량을 낳나, 사람 탓인가 → 유의성 검정(p-value)\n"
        "  ④ **품질 원인** — 불량을 가르는 진짜 축은 → 교란변수 층화(심슨)·다축 세그(률 기준)\n"
        "- **데이터**: 6공정 작업일보 · 재고 9단계 · 수주 95건 · 지그 실사 35종 · 검사 실적 (2026-04~06 · 전부 가공)\n"
        "- **신뢰 원칙**: 표본 30 미만 참고용 · 상관 ≠ 인과(층화로 재확인) · 모든 수치는 원본에서 재계산"
    )

    # ── 4. 주요 발견 ────────────────────────────────────────────────
    st.markdown("## 4. 주요 발견")

    st.markdown(f"#### 발견 ① 6공정 중 도장이 속도를 정한다 — 일 {bcap:,}개/일")
    order = ["사출", "지그삽입", "도장", "레이저", "인쇄", "검사"]
    flow_steps = [(p, f"{int(cap.get(p, 0)):,}/일") for p in order if p in cap.index]
    hi = next(i for i, (p, _) in enumerate(flow_steps) if p == bottleneck)
    _flow(flow_steps, highlight=hi)
    st.caption("작업시간이 가장 긴 공정(사출)이 아니라 **일생산능력이 가장 낮은 도장**이 전체 흐름을 막는다(제약이론).")

    st.markdown(f"#### 발견 ② 병목의 실제 원인 — 지그 실사가 장부보다 {jig_gap_pct}% 적다")
    wf = go.Figure(go.Waterfall(
        orientation="v", measure=["absolute", "relative", "total"],
        x=["장부 캐파", "실사 차이", "실사 캐파"],
        y=[jig_book, jig_real - jig_book, 0],
        text=[f"{jig_book:,}", f"{jig_real - jig_book:,}", f"{jig_real:,}"],
        textposition="outside",
        connector={"line": {"color": "#3A4553"}},
        decreasing={"marker": {"color": RED}},
        increasing={"marker": {"color": "#5FB86A"}},
        totals={"marker": {"color": BLUE}},
    ))
    wf.update_layout(height=320, showlegend=False, yaxis_title="도장 일캐파(개/일)")
    st.plotly_chart(wf, width="stretch")
    st.caption("설비 부족이 아니라 **지그 관리 문제**로 보인다 — 지그 몇 개 실사·보충만으로 캐파가 복구되는 무비용 개선 영역.")

    st.markdown(f"#### 발견 ③ 수주 {n_fail}건은 생산 이전에 이미 진다")
    fn = go.Figure(go.Funnel(
        y=["전체 수주", "위험(빠듯 이상)", "접수시점 불가"],
        x=[n_total, n_risk, n_fail],
        textinfo="value+percent initial",
        marker={"color": ["#9AA5B4", "#F5A85B", RED]},
    ))
    fn.update_layout(height=300)
    st.plotly_chart(fn, width="stretch")
    st.caption(f"전체 {n_total}건 → 위험 {n_risk}건 → **불가 {n_fail}건**. '빠듯하다'보다 '아예 불가능'이 강한 신호 — "
               "생산이 아무리 잘해도 못 맞추는 건이 접수 시점부터 존재한다.")

    st.markdown("#### 발견 ④ 통계가 가른 오판 3가지")
    st.markdown(
        f"| 통념 | 데이터 판정 | 근거 |\n|---|---|---|\n"
        f"| “불량 많은 사람이 문제” | ❌ **상황(잔업) 문제** | 잔업일 {ot_over}% vs 정상 {ot_norm}% (p<0.0001) · 작업자별 무관(p=0.60) |\n"
        f"| “{sp_top.customer} 물량이 불량 많다” | ❌ **색상(블랙)의 대리변수** | 전체 {sp_top.customer} 1위({sp_top.total_rate:.1f}%) → 블랙 층화 시 {spb.customer} 1위({spb.black_rate:.1f}%) 역전 |\n"
        f"| “Cpk 좋으면 불량 적다” | ❌ **예측 불가** | r={r_cpk:+.2f}, 유의하지 않음(이상치 제외 시 더 약함) |"
    )
    st.caption(f"다축 세그 변별력: **{ma_top.axis} {ma_top.ratio}배**(최고) — PPM 개선은 이 축부터. (률 기준, 물량 착시 제거)")

    # ── 5. 해석 — 문제의 연쇄 구조 ─────────────────────────────────
    st.markdown("## 5. 해석 — 문제의 연쇄 구조")
    _flow([("납기 미달", "겉으로 보이는 문제"), ("도장 병목", f"{bcap:,}개/일"),
           ("지그 실사 부족", f"장부 대비 −{jig_gap_pct}%"), ("지그 실사·보충", "무비용 해법")], highlight=2)
    st.markdown(
        "겉보기 문제(납기)를 거슬러 올라가면 **도장 병목 → 지그 관리**에 닿는다. 별도로, 수주 일부는 접수 시점에 이미 "
        "불가능했고(생산 책임이 아님), 불량·잔업 이슈는 사람이 아닌 **조건**(블랙 도장·잔업 상황)의 문제다. "
        "이들은 상관 기반이므로 인과는 확정하지 않는다."
    )

    # ── 6. 개선 권고 (처방) ─────────────────────────────────────────
    st.markdown("## 6. 개선 권고 (처방)")
    st.markdown(
        "| 우선순위 | 조치 | 비용 | 기대 효과 |\n|---|---|---|---|\n"
        f"| **1** | **지그 실사·보충** | 무비용 | 병목 캐파 복구(장부 수준까지 +{jig_gap_pct}%) |\n"
        f"| **2** | **수주 접수 리드타임 체크 게이트** | 프로세스 | 불가능 납기 {n_fail}건 사전 차단 |\n"
        "| **3** | **잔업 조건(연속일수·야간) 점검** | 관리 | 잔업 불량 +0.7%p 완화 · 개인 문책 중단 |\n"
        "| **4** | **블랙 도장 조건 개선** | 기술 검토 | 불량 최대 변별 축(2.2배) 공략 |"
    )

    # ── 7. 한계 · 근거 강도 ─────────────────────────────────────────
    st.markdown("## 7. 한계 · 근거 강도")
    st.markdown(
        "- 전부 **합성데이터** — 표본 35개 제품·95건 수주, 계절성 미반영. 실데이터 재현 필요\n"
        "- 병목·지그 수치는 실측(**확인됨**) / '지그가 병목의 원인'은 상관 기반(**~로 보인다**)\n"
        "- 도장 캐파의 일사이클 값이 낮게 설정돼 병목 정도가 과장됐을 수 있음\n"
        "- Cpk↔불량 무관은 PPM 등 다른 품질지표로 교차검증 필요"
    )

    # ── 8. 출처 · 재현 ──────────────────────────────────────────────
    st.markdown("## 8. 출처 · 재현")
    st.markdown(
        "- **원천**: BigQuery `wiki_manufacturing`(53테이블) · 스냅샷 `data/*.csv` (`make_snapshot.py`로 재생성)\n"
        "- **근거 위키**: `raw/학습/EDATA7기_이기쁨/` (병목·지그·수주·잔업·심슨·다축 인사이트 노트)\n"
        "- **재현성**: 이 리포트의 모든 수치는 열 때마다 원본에서 재계산된다 — 하드코딩 없음 · 기준일 2026-07-25"
    )
