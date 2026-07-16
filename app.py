# -*- coding: utf-8 -*-
"""우리는 왜 납기를 못 맞추는가 — 생산 리드타임 진단 대시보드.

데이터기반의사결정 7기 · 2주차 프로젝트 · 이기쁨
사출 → 지그삽입 → 도장 → 레이저 → 인쇄 → 검사 · 데이터 전부 가공(합성)

설계 원칙(교안 v2): 6개 차트가 모두 하나의 질문에 답한다. 결론을 텍스트로 박지 않고
차트가 스스로 드러내게 한다. 모든 수치는 매번 원본 CSV를 직접 읽어 재계산한다.

로컬 실행:  py -m streamlit run app.py
배포:       GitHub push → Streamlit Community Cloud (Main file path = app.py)
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="우리는 왜 납기를 못 맞추는가", page_icon="🏭", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


# ── 원본 데이터 ────────────────────────────────────────────────────────
do, jig, inv = load("daily_output"), load("jig_master"), load("inventory")
lt, dd, ri, pg = load("lot_trace"), load("defect_detail"), load("resource_inventory"), load("paint_grouping")

# 체인: 자재로트의 불량 반복 횟수 → 완제품 리드타임
lt["리드타임"] = (pd.to_datetime(lt.완제품일) - pd.to_datetime(lt.사출일)).dt.days
lt["불량횟수"] = lt.자재로트.map(dd.groupby("자재로트").size()).fillna(0)
lt["구간"] = lt.불량횟수.apply(lambda n: "0회" if n == 0 else ("1회" if n == 1 else "2회 이상"))
avg_lead = lt.리드타임.mean()
cap = do.groupby("공정").일생산가능수량.mean().sort_values()

# ── 헤더 · 기준값 (모든 차트의 기준선) ────────────────────────────────
st.title("🏭 우리는 왜 납기를 못 맞추는가")
st.caption("사출 → 지그삽입 → 도장 → 레이저 → 인쇄 → 검사 · 생산 리드타임 진단 · **데이터 전부 가공(합성)**")

c1, c2, c3 = st.columns(3)
c1.metric("평균 완제품 리드타임", f"{avg_lead:.1f}일")
c2.metric(f"병목 공정 일생산능력 ({cap.index[0]})", f"{int(cap.iloc[0]):,}개/일")
c3.metric("자재 안전재고 미달", f"{(ri.sort_values('기준일').groupby('자재코드').last().부족여부 == 'Y').mean() * 100:.0f}%")

st.divider()

# ── ① 어느 공정이 우리 속도를 정하는가 ────────────────────────────────
st.subheader("① 어느 공정이 우리 속도를 정하는가")
cdf = cap.reset_index(name="일생산능력")
cdf["구분"] = ["가장 느림" if i == 0 else "여유" for i in range(len(cdf))]
fig1 = px.bar(cdf, x="공정", y="일생산능력", color="구분", log_y=True, text="일생산능력",
              color_discrete_map={"가장 느림": "crimson", "여유": "lightslategray"},
              labels={"일생산능력": "일생산능력 (개/일 · 로그축)"})
fig1.update_layout(font=dict(size=13))
st.plotly_chart(fig1, width="stretch")

# ── ② 그 공정의 능력은 장부와 실사가 같은가 ───────────────────────────
st.subheader("② 그 공정의 능력은 장부와 실사가 같은가")
jdf = pd.DataFrame({"기준": ["장부 지그 기준", "실사 지그 기준"],
                    "도장 일캐파": [int(jig.도장일캐파_장부.sum()), int(jig.도장일캐파_실사.sum())],
                    "지그 수": [int(jig.장부지그수.sum()), int(jig.실사지그수.sum())]})
fig2 = px.bar(jdf, x="기준", y="도장 일캐파", color="기준", text="도장 일캐파", hover_data=["지그 수"],
              color_discrete_map={"장부 지그 기준": "lightslategray", "실사 지그 기준": "crimson"},
              labels={"도장 일캐파": "도장 일캐파 (개/일)"})
fig2.update_layout(font=dict(size=13), showlegend=False)
st.plotly_chart(fig2, width="stretch")

# ── ③ 그 능력을 색상 교체가 얼마나 먹는가 ─────────────────────────────
st.subheader("③ 그 능력을 색상 교체가 얼마나 먹는가")
pgs = pg.sort_values("생산일자")
fig3 = go.Figure()
fig3.add_bar(name="품번 개별 생산", x=pgs.생산일자, y=pgs.개별교체분, marker_color="crimson")
fig3.add_bar(name="색상 묶음 생산", x=pgs.생산일자, y=pgs.묶음교체분, marker_color="seagreen")
fig3.update_layout(barmode="group", font=dict(size=13), xaxis_title="생산일자",
                   yaxis_title="도장 색상 교체 손실(분)")
st.plotly_chart(fig3, width="stretch")

# ── ④ 불량이 반복되면 리드타임이 밀리는가 (체인 분석) ─────────────────
st.subheader("④ 불량이 반복되면 리드타임이 밀리는가")
band = (lt.groupby("구간").agg(로트수=("완제품로트", "size"), 평균리드타임=("리드타임", "mean"))
        .round(2).reindex(["0회", "1회", "2회 이상"]).reset_index())
fig4 = px.bar(band, x="구간", y="평균리드타임", color="구간", text="평균리드타임", hover_data=["로트수"],
              color_discrete_map={"0회": "lightslategray", "1회": "lightslategray", "2회 이상": "crimson"},
              labels={"구간": "그 자재로트에서 불량이 발생한 횟수", "평균리드타임": "사출 → 완제품 리드타임(일)"})
fig4.add_hline(y=avg_lead, line_dash="dash", line_color="gray", annotation_text=f"전체 평균 {avg_lead:.1f}일")
fig4.update_layout(font=dict(size=13), showlegend=False)
st.plotly_chart(fig4, width="stretch")

# ── ⑤ 자재가 발목을 잡는가 ────────────────────────────────────────────
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

# ── ⑥ 재고는 어느 공정 앞에 쌓여 있는가 ───────────────────────────────
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

st.divider()
st.caption("데이터기반의사결정 7기 · 이기쁨 | 데이터 전부 가공(합성) — 실 회사 데이터와 무관 "
           "| 분석 근거 원본: 볼트 위키 `raw/학습/EDATA7기_이기쁨/`")
