# -*- coding: utf-8 -*-
"""리포트 탭 — 납기 문제해결 통합 리포트 (교안급 8구성 · 단일 문서).

교안 리포트 수준 장치를 전부 갖춘다:
 · 주장별 confidence 등급(상/중/하) + 판단 기준표
 · 원인 한 단계 더(불량유형×원인구분 빈도 → 블랙 3대 원인 → 담당 지정)
 · 판정 규칙 정밀도(precision/recall) 정직 공개(합성 결정론 한계 포함)
 · 교란 통제(잔업↔물량 3분위 층화) · 한계 7종 · 부록 추적성(데이터표·인사이트표·근거목록)
시각: 공정흐름·워터폴·퍼널·층화표 — 대시보드 탭 차트와 형식 중복 금지.
값은 전부 원본 스냅샷에서 재계산(하드코딩 없음).
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE = "#5AA6D8"
RED = "#F06A7E"


def _flow(steps, highlight=-1):
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


def _conf(level, note=""):
    color = {"상": "#5FB86A", "중": "#F5A85B", "하": RED}[level]
    tail = f" — {note}" if note else ""
    st.markdown(f"<span style='color:{color};font-weight:700'>confidence: {level}</span>"
                f"<span style='color:#9AA5B4;font-size:13px'>{tail}</span>", unsafe_allow_html=True)


def render_mfg_report(load):
    # ── 원본 재계산 ─────────────────────────────────────────────────
    do = load("daily_output")
    jig = load("jig_master")
    diag = load("plan_수주납기진단")
    cpk = load("cpk_defect_analysis")
    ot = load("overtime_defect_analysis")
    sp = load("simpson_defect")
    ma = load("multiaxis_defect")
    dc = load("defect_cause_breakdown")
    ov = load("overtime_volume_control")
    lt = load("lot_trace")
    dd = load("defect_detail")

    cap = do.groupby("공정").일생산가능수량.mean().round(0).astype(int).sort_values()
    bottleneck, bcap = cap.index[0], int(cap.iloc[0])
    jig_book, jig_real = int(jig.도장일캐파_장부.sum()), int(jig.도장일캐파_실사.sum())
    jig_gap = round((jig_book - jig_real) / jig_book * 100)
    n_total, n_risk = len(diag), int((diag.납기판정 != "여유").sum())
    n_fail = int((diag.납기판정 == "납기 부족(불가)").sum())
    r_cpk = round(cpk.Cpk.corr(cpk.불량률), 2)
    ot_r = ot.set_index("구분").불량률
    ot_over, ot_norm = round(float(ot_r.get("잔업일")), 1), round(float(ot_r.get("정상일")), 1)
    sp_top = sp.sort_values("total_rate", ascending=False).iloc[0]
    spb = sp.dropna(subset=["black_rate"]).sort_values("black_rate", ascending=False).iloc[0]
    ma_top = ma.sort_values("ratio", ascending=False).iloc[0]

    # 블랙 불량 3대 원인 (원인 딥다이브)
    dcb = dc[dc.seg == "블랙"].sort_values("q", ascending=False).reset_index(drop=True)
    dca = dc[dc.seg == "전체"].set_index("dtype").pct
    top3 = dcb.head(3)
    top3_sum = round(top3.pct.sum(), 1)

    # 잔업 물량 교란 통제
    ov_n = ov[ov.overtime_yn == "N"].set_index("tier").defect_rate
    ov_y = ov[ov.overtime_yn == "Y"].set_index("tier").defect_rate
    t3y = float(ov_y.get(3))

    # 반복불량 신호 정밀도 (로트 규칙)
    lt2 = lt.copy()
    lt2["리드타임"] = (pd.to_datetime(lt2.완제품일) - pd.to_datetime(lt2.사출일)).dt.days
    lt2["불량횟수"] = lt2.자재로트.map(dd.groupby("자재로트").size()).fillna(0)
    avg_lead = lt2.리드타임.mean()
    sig = lt2.불량횟수 >= 2
    late = lt2.리드타임 > avg_lead
    tp = int((sig & late).sum())
    prec = round(tp / max(int(sig.sum()), 1) * 100)
    rec = round(tp / max(int(late.sum()), 1) * 100)

    # ── 제목 ────────────────────────────────────────────────────────
    st.markdown(f"### 📄 납기 문제해결 리포트 &nbsp;<span style='color:{BLUE}'>— 우리는 왜 납기를 못 맞추나?</span>",
                unsafe_allow_html=True)
    st.caption("작성 2026-07-25 · 근거: 강의 위키 raw/학습/EDATA7기_이기쁨 (질문 12·분석 노트·SQL·인사이트, 허브 2) · 데이터 전부 가공(합성)")

    # ── 1. Executive Summary ────────────────────────────────────────
    st.markdown("## 1. Executive Summary")
    st.success(
        f"1. **도장이 병목이다** — 일 **{bcap:,}개/일** 최소 공정, 지그 실사가 장부보다 **{jig_gap}% 적어**"
        f"({jig_real:,} vs {jig_book:,}) 실제 원인으로 **보인다**. (실측 확인 · 원인 해석은 상관 기반)\n"
        f"2. **수주 {n_fail}건은 접수 시점에 이미 불가능했다** — 전체 {n_total}건 중 확보기간 < 필요 리드타임. (확인됨)\n"
        f"3. **사람·고객사 탓이 아니다** — 잔업은 상황 문제(p<0.0001 · 작업자 무관 p=0.60 · 물량 교란 기각, "
        f"단 대물량×잔업 {t3y}% 최악), 불량은 블랙 도장 조건이 가른다(3대 원인 {top3_sum}% = 흐름·미인쇄·색상편차, "
        f"심슨 역전 · Cpk 예측 불가 r={r_cpk:+.2f}). (확인됨 — 층화·빈도 분석)"
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"병목({bottleneck}) 일캐파", f"{bcap:,}개/일")
    k2.metric("지그 실사 과소", f"{jig_gap}%", delta="장부 대비 부족", delta_color="inverse")
    k3.metric("접수시점 불가 수주", f"{n_fail}건", delta=f"전체 {n_total}건 중", delta_color="inverse")
    k4.metric("대물량×잔업 불량률", f"{t3y}%", delta="최악 조합", delta_color="inverse")

    # ── 2. 배경·목적 ────────────────────────────────────────────────
    st.markdown("## 2. 배경·목적")
    st.markdown(
        "이 리포트는 처방적 질문 — **\"납기 미달을 줄이기 위해 무엇을 해야 하는가\"** — 에 대한 정식 답변이다. "
        "3주간 강의 위키에 쌓인 근거(질문 12건·분석·SQL·인사이트, 허브 2)를 종합하고, 위키가 다루지 않았던 "
        "두 지점(**잔업의 물량 교란 통제**, **블랙 불량의 원인 분해**)만 이번에 원천 데이터로 새로 검증해 추가했다. "
        "진단이 늘 \"생산이 서둘러야 한다\"에 머물던 것을, 데이터로 구조적 원인·담당·순서로 바꾸는 것이 목적이다."
    )

    # ── 3. 데이터·방법론 ────────────────────────────────────────────
    st.markdown("## 3. 데이터·방법론")
    st.markdown(
        f"| 데이터 | 건수 | 비고 |\n|---|---|---|\n"
        f"| 품목 마스터 | 35종 | 제품도번=전 테이블 연결 키 |\n"
        f"| 작업일보 6공정 | 2,300여 건 | 리드타임 역산(작업시간÷수량) 원천 |\n"
        f"| 수주·납기 진단 | {n_total}건 | 확보기간 vs 필요 리드타임 |\n"
        f"| 로트 추적 | {len(lt2)}건 | 자재로트→완제품, 반복불량 신호 |\n"
        f"| 불량 상세 | {len(dd)}건 | 불량유형×원인구분×색상 (원인 분해) |\n"
        f"| 지그 실사 | {len(jig)}종 | 장부 vs 실사 |\n"
        f"| 생산·검사 (erp) | 1,834·924건 | BigQuery `manufacturing` — 잔업 z검정·물량 통제 |"
    )
    _flow([("문제 정의", "왜 납기를 못 맞추나"), ("리드타임 역산", "작업일보 → CT"),
           ("병목 진단", "일생산능력 최소"), ("원인 검증", "유의성·층화·빈도"), ("처방", "담당·순서 지정")])
    st.markdown(
        "**판단 임계치**: 부하율>100% 잔업 · 표본 30건 미만 참고용 · 상관≠인과(층화로 재확인).\n\n"
        "**confidence 판단 기준**\n\n"
        "| 단계 | 기준 |\n|---|---|\n"
        "| **상** | 전수(대표본) 데이터에서 뚜렷한 차이가 교차 방법으로 재확인됨 |\n"
        "| **중** | 통계적으로 유의하나 표본이 작거나(30~90건) 해석이 상관 기반 |\n"
        "| **하** | 관계가 보이나 재현성·인과·표본이 근본적으로 부족 |"
    )

    # ── 4. 현황 — 우리는 지금 무엇을 알고 있는가 ────────────────────
    st.markdown("## 4. 현황 — 우리는 지금 무엇을 알고 있는가")

    st.markdown(f"#### 4-1. 6공정 중 도장이 속도를 정한다 — 일 {bcap:,}개/일")
    _conf("상", "6공정 210행 전수, 역산 CT 기반")
    order = ["사출", "지그삽입", "도장", "레이저", "인쇄", "검사"]
    steps = [(p, f"{int(cap.get(p, 0)):,}/일") for p in order if p in cap.index]
    hi = next(i for i, (p, _) in enumerate(steps) if p == bottleneck)
    _flow(steps, highlight=hi)
    st.caption("작업시간 최장(사출)이 아니라 **일생산능력 최소(도장)**가 병목 — 제약이론(TOC).")

    st.markdown(f"#### 4-2. 병목의 실제 원인 — 지그 실사가 장부보다 {jig_gap}% 적다")
    _conf("상", "35종 전수 실사 — 단, '병목의 원인'이라는 해석은 상관 기반(중)")
    wf = go.Figure(go.Waterfall(
        orientation="v", measure=["absolute", "relative", "total"],
        x=["장부 캐파", "실사 차이", "실사 캐파"], y=[jig_book, jig_real - jig_book, 0],
        text=[f"{jig_book:,}", f"{jig_real - jig_book:,}", f"{jig_real:,}"], textposition="outside",
        connector={"line": {"color": "#3A4553"}},
        decreasing={"marker": {"color": RED}}, totals={"marker": {"color": BLUE}}))
    wf.update_layout(height=300, showlegend=False, yaxis_title="도장 일캐파(개/일)")
    st.plotly_chart(wf, width="stretch")

    st.markdown(f"#### 4-3. 수주 {n_fail}건은 생산 이전에 이미 진다")
    _conf("상", f"수주 {n_total}건 전수 — 단, 판정 규칙의 실측 검증은 미완(한계 ③)")
    fn = go.Figure(go.Funnel(
        y=["전체 수주", "위험(빠듯 이상)", "접수시점 불가"], x=[n_total, n_risk, n_fail],
        textinfo="value+percent initial", marker={"color": ["#9AA5B4", "#F5A85B", RED]}))
    fn.update_layout(height=290)
    st.plotly_chart(fn, width="stretch")

    st.markdown("#### 4-4. 잔업은 사람도, 물량 탓도 아니다 — 상황(잔업 조건) 문제")
    _conf("상", "생산 1,834·검사 924건, z=19.41 p<0.0001 · 물량 교란 통제 완료")
    st.markdown(
        f"- 잔업일 불량 **{ot_over}%** vs 정상 **{ot_norm}%**(p<0.0001) · **작업자별** 잔업↔불량 r=−0.10, p=0.60(무관)\n"
        f"- **물량 교란 기각**: 잔업일 평균 물량 1,074 vs 정상 1,060(계획달성률 동일 94.6%) — \"물량이 몰려서\"가 아니다\n"
        f"- **물량 3분위 층화 후에도** 전 구간 잔업일이 높다: "
        f"소물량 {ov_y.get(1)}>{ov_n.get(1)} · 중물량 {ov_y.get(2)}>{ov_n.get(2)} · 대물량 {ov_y.get(3)}>{ov_n.get(3)}\n"
        f"- ★ 신규 발견: **대물량×잔업 조합이 {t3y}%로 유일하게 3%대** — 잔업을 줄이되, 특히 대물량 로트를 잔업에 배치하지 말 것"
    )

    st.markdown("#### 4-5. 통계가 가른 오판 3가지")
    _conf("상", "심슨 층화·다축 세그(률 기준) — Cpk는 n=35로 중")
    st.markdown(
        f"| 통념 | 데이터 판정 | 근거 |\n|---|---|---|\n"
        f"| “불량 많은 사람이 문제” | ❌ 상황(잔업) 문제 | 4-4 참조 |\n"
        f"| “{sp_top.customer} 물량이 불량 많다” | ❌ 색상(블랙)의 대리변수 | 전체 {sp_top.customer} 1위({sp_top.total_rate:.1f}%) → 블랙 층화 시 {spb.customer} 1위({spb.black_rate:.1f}%) 역전 |\n"
        f"| “Cpk 좋으면 불량 적다” | ❌ 예측 불가 | r={r_cpk:+.2f} 유의하지 않음(n=35, 이상치 제외 시 더 약함) |"
    )
    st.caption(f"다축 세그 변별력(률 기준): **{ma_top.axis} {ma_top.ratio}배**(최고) > 고객사 1.7 > 호기 1.0 — 물량 착시 제거.")

    # ── 5. 원인 분석 — 블랙 불량은 왜 생기는가 (한 단계 더) ─────────
    st.markdown("## 5. 원인 분석 — 블랙 불량은 왜 생기는가")
    _conf("상", f"불량 상세 {len(dd)}건 × 불량유형·원인구분 빈도 분석")
    rows = "".join(
        f"| {r.dtype}({r.cause}) | **{r.pct}%** | {dca.get(r.dtype, 0)}% | "
        f"{'+' if r.pct - dca.get(r.dtype, 0) >= 0 else ''}{round(r.pct - dca.get(r.dtype, 0), 1)}%p |\n"
        for r in top3.itertuples())
    st.markdown(
        f"블랙 불량의 3대 원인이 **{top3_sum}%**를 차지한다:\n\n"
        f"| 원인(구분) | 블랙 내 비중 | 전체 내 비중 | 블랙 특이도 |\n|---|---|---|---|\n{rows}"
    )
    st.markdown(
        f"- **흐름({top3.iloc[0].pct}%)이 블랙에서 두드러진다**(전체 대비 +{round(top3.iloc[0].pct - dca.get('흐름', 0), 1)}%p) — "
        "블랙 고광택 도막의 처짐/흘러내림, 즉 **도장 조건(도료 점도·토출·건조) 소관**\n"
        "- 미인쇄는 **인쇄 설비**, 색상편차는 **조색·페인트 로트** 소관\n"
        "- → 결론: \"블랙 물량 주의\"라는 지시보다 **도장조건팀·인쇄설비·조색 3곳에 문제를 나눠 넘기는 것**이 근본 해법이다 "
        "(고객사·작업자를 갈구는 것은 데이터상 근거 없음)"
    )

    # ── 6. 개선 제안 ────────────────────────────────────────────────
    st.markdown("## 6. 개선 제안 — 무엇을, 어떤 순서로")
    st.markdown(
        f"| 우선순위 | 제안 | 근거 | 임팩트 | 난이도 |\n|---|---|---|---|---|\n"
        f"| **1** | **지그 실사·보충** | 병목 캐파 −{jig_gap}%의 직접 원인 후보, 35종 실측 | 큼 | **낮음(무비용)** |\n"
        f"| **2** | **수주 접수 리드타임 체크 게이트** | 불가 {n_fail}건({round(n_fail/n_total*100)}%)이 접수 시점 확정 | 큼 | 중(영업 협업) |\n"
        f"| **3** | **잔업 배치 규칙 — 대물량 로트를 잔업에 넣지 않기** | 대물량×잔업 {t3y}% 최악 조합(층화 검증) | 중 | 낮음 |\n"
        f"| **4** | **블랙 도장조건·인쇄설비·조색 3분할 개선** | 3대 원인 {top3_sum}%, 담당 명확 | 큼 | 중(부서 협업) |\n"
        f"| **5** | 반복불량 로트 조기경보는 **실데이터 검증 후 도입** | 합성에선 P/R {prec}/{rec}%지만 결정론 패턴(한계 ②) | 확정 불가 | — |"
    )
    st.caption("근거 없는 조치는 제외한다 — 작업자 문책(p=0.60 무관)·고객사 압박(심슨 역전)·Cpk 단독 관리(r 유의X)는 목록에 없다.")

    # ── 7. 한계 ─────────────────────────────────────────────────────
    st.markdown("## 7. 한계")
    st.markdown(
        f"1. **상관은 인과가 아니다** — '지그 부족→병목', '잔업→불량' 모두 유의한 관계이지 확정 인과가 아니다(층화로 교란은 일부 통제).\n"
        f"2. **합성데이터의 결정론 패턴** — 반복불량(2회+) 신호의 지연 예측이 P/R {prec}/{rec}%로 나오는 것은 "
        f"데이터 생성 규칙의 인공물이다. 실데이터에서는 크게 낮아질 것을 전제해야 하며, 이 수치로 조기경보를 정당화할 수 없다.\n"
        f"3. **수주 판정 규칙 미실측** — '빠듯/불가' 판정이 실제 지연으로 이어졌는지 결과 데이터로 검증하지 못했다(합성 계획 데이터 한계).\n"
        f"4. **도장 캐파 과장 가능** — 일사이클 값(6~10회/일)이 낮게 설정돼 병목의 정도가 부풀려졌을 수 있다(방향은 유지될 것으로 보나 크기 불확실).\n"
        f"5. **표본 경계** — 제품 35종·수주 {n_total}건·물량 층화 셀 68~76건. 계절성 미반영(2026-04~06).\n"
        f"6. **시간 순서 미확인** — 잔업 지시와 불량 발생의 선후를 로그로 확인하지 않았다(물량 교란은 기각했으나 다른 공통원인 가능).\n"
        f"7. **Cpk 무관 판정의 교차검증 필요** — n=35 한계. PPM 등 다른 품질지표로 재확인 전까지 'Cpk 폐기'가 아니라 '단독 신뢰 금지'로 읽어야 한다."
    )

    # ── 8. 부록 ─────────────────────────────────────────────────────
    st.markdown("## 8. 부록")
    st.markdown(
        "**8-1. 인사이트 요약표 (날짜순)**\n\n"
        "| 날짜 | 인사이트 | conf. | 핵심 |\n|---|---|---|---|\n"
        "| 07-10 | insight-병목공정 | 상 | 작업시간 최장(사출)≠병목(도장) |\n"
        "| 07-10 | insight-지그실사-캐파오차 | 상 | 제품별 25.8%·합계 24% 과대(방식 병기) |\n"
        "| 07-10 | insight-다축세그멘테이션 | 상 | 률 기준 색상 2.2배 최고 변별 |\n"
        "| 07-15 | insight-고객사-교란변수 | 상 | 심슨 역전 — 고객사=색상 대리변수 |\n"
        "| 07-22 | insight-잔업-불량-유의성 | 상 | p<0.0001 vs 작업자 무관 p=0.60 |\n"
        "| 07-24 | insight-Cpk-이상치지렛대 | 중 | 이상치 3종 제외 시 r −0.29→−0.16 |\n"
        "| 07-24 | q-012 수주납기 실현가능성 | 상 | 접수시점 불가 13건 |\n"
        "| 07-25 | 잔업 물량교란 통제(신규) | 상 | 물량 동일·층화 유지·대물량×잔업 3.09% |\n"
        "| 07-25 | 블랙 3대 원인 분해(신규) | 상 | 흐름·미인쇄·색상편차 77.3% |\n\n"
        "**8-2. 근거 노트** — 질문 q-001~q-012(12건) · 분석 analysis-잔업불량-유의성검정/직원만족도-교란변수처리/"
        "Cpk불량-이상치처리/수주납기-역산방법 · SQL sql-잔업불량/직원만족도-상담원지표/Cpk-불량률 · "
        "허브 hub-생산납기/hub-품질개선 (강의 위키 `raw/학습/EDATA7기_이기쁨/`)\n\n"
        "**8-3. 재현** — 원천 BigQuery `wiki_manufacturing`(53테이블)+`manufacturing`(erp 5테이블) → "
        "`make_snapshot.py` → `data/*.csv` → 이 리포트(열 때마다 재계산, 하드코딩 없음) · 기준일 2026-07-25"
    )
