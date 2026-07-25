# 🏭 제조 납기 관리 대시보드 — 강의 실습(CS) → 실무형 변환(제조)

> 모두의연구소 **데이터기반의사결정 7기** · 이기쁨 · **데이터 전부 가공(합성)**
> 강의(CS 고객이탈)에서 배운 **2·3주차 전 기법**을 내 제조 현장 데이터로 실무형 변환한 대시보드.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py          # http://localhost:8501
```

> Windows에서 `streamlit`이 PATH에 없으면 → `py -m streamlit run app.py`

## 구조 (상위탭 2단 · 중첩 멀티탭)

```
🎓 강의 원본 실습 (CS)
  ├ 📊 분석 — 고객이탈 6차트(VOC·채널·재문의·요금제·지역·이용량)
  │         + VOC 텍스트분석 + 체인분석 퍼널 + 상담원 통계(eNPS·번아웃×CSAT·교육이수) + 팀 필터
  └ 📄 리포트 — 상위 1% 리포트(BLUF·KPI·Action Title·So-What·한계) + 8구성 줄글 리포트

🏭 실무형 변환 (제조)
  ├ 🩺 납기 진단 — 6차트(병목·지그·색상교체·반복불량·자재·재고)
  ├ 🗓️ 공정별 계획서 — 납기 역산 + 공정 선택 위젯
  ├ 📅 수주 납기 진단 — 접수 시점 실현 가능성
  ├ 📊 강의 통계기법 재현 — Cpk·잔업(상관·p-value·이상치) + 심슨의 역설 + 다축 세그멘테이션
  └ 📄 리포트 — 상위 1% 리포트 + 8구성 줄글 리포트
```

강의에서 배운 모든 기법(상관계수·p-value·추세선·이상치 지렛대·평균의 함정·지표결합·가설소거·체인분석·심슨역설·다축세그·BLUF·8구성 리포트·멀티탭)이 CS와 제조 양쪽에 대응됩니다.

## BigQuery 파이프라인 (내재화)

```
BigQuery 원천(study · wiki_manufacturing) → make_snapshot.py → data/ 스냅샷 CSV → 대시보드
```

- **🟢 라이브 / 🟡 스냅샷 자동 폴백** — BigQuery 인증이 있으면 라이브 감지, 없으면 사전 스냅샷으로 정상 렌더(배포 안전, `DEPLOY.md` 방식)
- **스냅샷 갱신**: `py -X utf8 make_snapshot.py` (원천이 바뀌면 한 번 실행 → data/ 재생성)
- 모든 값은 원본에서 **재계산 — 하드코딩 없음**

## 파일

```
app.py            메인 (상위탭·하위탭 구조, 원본 재계산)
reports.py        리포트 탭 로직 (상위 1% 리포트 기법)
make_snapshot.py  BigQuery → 스냅샷 파이프라인
data/             스냅샷 CSV (lecture_*·제조 원천·simpson_defect·multiaxis_defect 등)
report/           8구성 줄글 비즈니스 리포트 (고객서비스·납기 문제해결)
DEPLOY.md         배포 가이드 (라이브/스냅샷 폴백·Python 3.12)
```

## 배포 (Streamlit Community Cloud)

`DEPLOY.md` 참고 — GitHub **public** push → [share.streamlit.io](https://share.streamlit.io) → Create app → Main file path `app.py` → **Advanced settings에서 Python 3.12** → Deploy. BigQuery 인증이 없어도 🟡 스냅샷으로 정상 동작합니다.

## 데이터에 대하여

모든 값은 시드를 고정해 생성한 **합성 데이터**입니다. 고객사는 A~E사 같은 가공명이며 실 회사·거래처·설비·자격증명 정보는 없습니다. 데이터에 심은 **패턴**(병목·지그 실사 부족·색상 교체 손실·반복 불량→리드타임 지연·색상 교란변수 등)은 실제 제조 현장 구조를 재현한 것입니다.

## 만든 사람

이기쁨 — 생산·제조 기술 / 모두의연구소 데이터기반의사결정 7기
