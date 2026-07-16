# 🏭 우리는 왜 납기를 못 맞추는가 — 제조 리드타임 진단 대시보드

> 모두의연구소 **데이터기반의사결정 7기 · 2주차 프로젝트** — 이기쁨
> 사출 → 지그삽입 → 도장 → 레이저 → 인쇄 → 검사
> **데이터는 전부 가공(합성)** — 실 회사 데이터·자격증명·실명 거래처 일절 없음

제조 현장의 진짜 질문 하나에 6개 차트가 답합니다. 결론을 글로 적어두지 않았습니다 —
차트를 훑는 것만으로 "아, 이래서 납기가 밀리는구나"가 보이도록 만들었습니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py          # http://localhost:8501
```

> Windows에서 `streamlit` 명령이 PATH에 없으면 → `py -m streamlit run app.py`

## 이 대시보드가 던지는 질문

| # | 질문 | 근거 데이터 |
|---|---|---|
| ① | 어느 공정이 우리 속도를 정하는가 | `daily_output` — 공정별 일생산능력(역산 CT 기반) |
| ② | 그 공정의 능력은 장부와 실사가 같은가 | `jig_master` — 도장 지그 장부 vs 실사 |
| ③ | 그 능력을 색상 교체가 얼마나 먹는가 | `paint_grouping` — 개별 생산 vs 색상 묶음 |
| ④ | **불량이 반복되면 리드타임이 밀리는가** | `lot_trace` × `defect_detail` — 자재로트 체인 |
| ⑤ | 자재가 발목을 잡는가 | `resource_inventory` — 안전재고 대비 현재고 |
| ⑥ | 재고는 어느 공정 앞에 쌓여 있는가 | `inventory` — 재고 파이프라인 9단계 |

**④가 이 대시보드의 핵심입니다.** "불량이 있었나(있음/없음)"로 보면 리드타임에 차이가 거의 없지만,
**"몇 번 반복됐나"로 쪼개면 결론이 뒤집힙니다** — 1회까지는 정상 범위인데, 2회 이상 반복된
자재로트는 리드타임이 확연히 길어집니다. 한 번의 불량은 사고지만 **반복되는 불량은
"문제가 해결되지 않고 있다"는 신호**이고, 그게 곧 납기 지연입니다.

## 구성

```
app.py              Streamlit 앱 — 매번 원본 CSV를 직접 읽어 재계산 (숫자 하드코딩 없음)
data/               합성 CSV 14개
requirements.txt    streamlit · pandas · plotly
```

## 배포 (Streamlit Community Cloud)

1. 이 저장소를 **public**으로 push (무료 플랜은 공개 저장소만 지원)
2. [share.streamlit.io](https://share.streamlit.io) → Sign in with GitHub → **Create app**
3. **Deploy a public app from GitHub** → Repository / Branch `main` / **Main file path `app.py`**
4. Deploy → 빌드 1~3분 → `https://<APP_NAME>.streamlit.app` 발급

## 데이터에 대하여

모든 값은 시드를 고정해 생성한 **합성 데이터**입니다. 고객사는 A~E사 같은 가공명이며 실제
회사·거래처·설비 정보는 들어 있지 않습니다. 다만 데이터에 심은 **패턴**(병목 공정, 지그 실사
부족, 색상 교체 손실, 자재로트 반복 불량 → 리드타임 지연)은 실제 제조 현장에서 관찰되는
구조를 재현한 것입니다.

## 만든 사람

이기쁨 — 생산·제조 기술 / 모두의연구소 데이터기반의사결정 7기
