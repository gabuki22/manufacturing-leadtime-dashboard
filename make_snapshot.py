# -*- coding: utf-8 -*-
"""BigQuery → 스냅샷 CSV 자동 생성 파이프라인 (BigQuery 내재화).

Day1(BigQuery)·Day5/DEPLOY.md 접목: BigQuery 원천에서 대시보드용 스냅샷을
미리 뽑아 data/ 에 저장 → 배포 환경(인증 없음)에서도 안전하게 렌더.

 · CS 집계 스냅샷: study 원천 → lecture_*.csv (쿼리로 재계산)
 · 제조 원천 스냅샷: manufacturing 원천 → data/*.csv (그대로 export)

로컬 gcloud ADC 인증 필요. 실행: py -X utf8 make_snapshot.py
값을 원본(BigQuery)에서 재계산 — 하드코딩 없음.
"""
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

PROJECT = "gen-lang-client-0109601387"
LOC = "asia-northeast3"
DATA = Path(__file__).parent / "data"
c = bigquery.Client(project=PROJECT)


def q(sql):
    return c.query(sql, location=LOC).to_dataframe()


# ── CS 집계 스냅샷 (study 원천 → lecture_*) ─────────────────────────
CS = {
    "lecture_voc_churn": """
        WITH voc_neg AS (SELECT DISTINCT customer_id FROM `study.data_voc`
                         WHERE category="해지관련" AND sentiment="부정")
        SELECT "전체 고객" AS grp, COUNT(*) AS n,
               ROUND(100.0*COUNTIF(churn_yn)/COUNT(*),1) AS churn_rate FROM `study.data_customers`
        UNION ALL
        SELECT "해지관련 부정VOC 있음", COUNT(*), ROUND(100.0*COUNTIF(churn_yn)/COUNT(*),1)
        FROM `study.data_customers` WHERE customer_id IN (SELECT customer_id FROM voc_neg)""",
    "lecture_plan_churn":
        'SELECT plan, COUNT(*) AS n, ROUND(100.0*COUNTIF(churn_yn)/COUNT(*),1) AS churn_rate '
        'FROM `study.data_customers` GROUP BY plan ORDER BY churn_rate DESC',
    "lecture_region_churn":
        'SELECT region, COUNT(*) AS n, ROUND(100.0*COUNTIF(churn_yn)/COUNT(*),1) AS churn_rate '
        'FROM `study.data_customers` GROUP BY region ORDER BY churn_rate DESC',
    "lecture_channel_csat":
        'SELECT c.channel, ROUND(AVG(s.csat),2) AS csat, '
        'ROUND(100.0*COUNTIF(c.is_recontact)/COUNT(*),1) AS recon_rate '
        'FROM `study.data_consultations` c LEFT JOIN `study.data_satisfaction` s '
        'ON c.consult_id=s.consult_id GROUP BY c.channel ORDER BY csat',
    "lecture_recontact_churn": """
        WITH recon AS (SELECT customer_id, COUNTIF(is_recontact) AS n
                       FROM `study.data_consultations` GROUP BY customer_id)
        SELECT CASE WHEN n=0 THEN "0회" WHEN n=1 THEN "1회" ELSE "2회 이상" END AS band,
               COUNT(*) AS n, ROUND(100.0*COUNTIF(c.churn_yn)/COUNT(*),1) AS churn_rate
        FROM recon r JOIN `study.data_customers` c ON r.customer_id=c.customer_id
        GROUP BY band ORDER BY band""",
    "lecture_tenure_usage": """
        WITH u AS (SELECT customer_id, ROUND(AVG(data_gb),1) AS avg_gb
                   FROM `study.data_usage_history` GROUP BY customer_id)
        SELECT c.customer_id, DATE_DIFF(DATE "2024-12-31", c.join_date, MONTH) AS tenure_months,
               u.avg_gb, c.churn_yn FROM `study.data_customers` c JOIN u ON c.customer_id=u.customer_id""",
    "lecture_voc_analysis":
        'SELECT category, sentiment, COUNT(*) AS n FROM `study.data_voc` '
        'GROUP BY category, sentiment ORDER BY category',
}

# ── 제조 파생 스냅샷 (조인·집계 쿼리 → 대시보드용) ─────────────────
MFG_Q = {
    "simpson_defect":
        'WITH j AS (SELECT m.`고객사` AS customer, m.`색상` AS col, w.`생산수량` AS p, w.`불량수량` AS d '
        'FROM `wiki_manufacturing.worklog_검사` w JOIN `wiki_manufacturing.master` m ON w.`제품도번`=m.`제품도번`) '
        'SELECT customer, ROUND(100.0*SUM(d)/SUM(p),2) AS total_rate, '
        'ROUND(100.0*SUM(IF(col="블랙",d,NULL))/NULLIF(SUM(IF(col="블랙",p,NULL)),0),2) AS black_rate, '
        'ROUND(100.0*SUM(IF(col="블랙",p,NULL))/SUM(p),1) AS black_ratio '
        'FROM j GROUP BY customer ORDER BY total_rate DESC',
    "multiaxis_defect":
        'WITH j AS (SELECT m.`색상` AS color, m.`고객사` AS customer, w.`호기라인` AS line, '
        'w.`생산수량` AS p, w.`불량수량` AS d '
        'FROM `wiki_manufacturing.worklog_검사` w JOIN `wiki_manufacturing.master` m ON w.`제품도번`=m.`제품도번`), '
        'color_r AS (SELECT color AS g, SUM(d)/SUM(p) AS r FROM j GROUP BY color), '
        'cust_r AS (SELECT customer AS g, SUM(d)/SUM(p) AS r FROM j GROUP BY customer), '
        'line_r AS (SELECT line AS g, SUM(d)/SUM(p) AS r FROM j GROUP BY line) '
        'SELECT "색상" AS axis, ROUND(MAX(r)/MIN(r),1) AS ratio, ROUND(MAX(r)*100,2) AS top_rate FROM color_r '
        'UNION ALL SELECT "고객사", ROUND(MAX(r)/MIN(r),1), ROUND(MAX(r)*100,2) FROM cust_r '
        'UNION ALL SELECT "호기라인", ROUND(MAX(r)/MIN(r),1), ROUND(MAX(r)*100,2) FROM line_r ORDER BY ratio DESC',
    "defect_cause_breakdown":
        'WITH j AS (SELECT d.`불량유형` AS dtype, d.`원인구분` AS cause, d.`불량수량` AS q, m.`색상` AS color '
        'FROM `wiki_manufacturing.defect_detail` d JOIN `wiki_manufacturing.master` m ON d.`제품도번`=m.`제품도번`) '
        'SELECT "전체" AS seg, dtype, cause, SUM(q) AS q, ROUND(100*SUM(q)/SUM(SUM(q)) OVER (PARTITION BY 1),1) AS pct '
        'FROM j GROUP BY dtype, cause '
        'UNION ALL SELECT "블랙", dtype, cause, SUM(q), ROUND(100*SUM(q)/SUM(SUM(q)) OVER (PARTITION BY 2),1) '
        'FROM j WHERE color="블랙" GROUP BY dtype, cause ORDER BY seg, q DESC',
    "overtime_volume_control":
        'WITH j AS (SELECT p.overtime_yn, p.prod_qty, q.inspect_qty, q.defect_qty, '
        'NTILE(3) OVER (ORDER BY p.prod_qty) AS tier '
        'FROM `manufacturing.production` p JOIN `manufacturing.quality` q ON p.production_id=q.production_id) '
        'SELECT tier, overtime_yn, COUNT(*) AS lots, ROUND(100.0*SUM(defect_qty)/SUM(inspect_qty),2) AS defect_rate '
        'FROM j GROUP BY tier, overtime_yn ORDER BY tier, overtime_yn',
}

# ── 제조 원천 스냅샷 (기존 wiki_manufacturing 원천 → data/*.csv, 한글 테이블명 그대로) ──
MFG = ["daily_output", "jig_master", "inventory", "lot_trace", "defect_detail", "resource_inventory",
       "paint_grouping", "plan_backward_전체", "plan_공정_지그삽입_로딩배분", "plan_자재소요",
       "plan_수주납기진단", "cpk_defect_analysis", "overtime_defect_analysis", "overtime_defect_by_process"]


def main():
    print("=== CS 집계 스냅샷 (study → lecture_*) ===")
    for name, sql in CS.items():
        df = q(sql)
        df.to_csv(DATA / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"  ✔ {name:26} {len(df):>4}행")
    print("=== 제조 원천 스냅샷 (wiki_manufacturing → data/*.csv) ===")
    for name in MFG:
        df = q(f"SELECT * FROM `wiki_manufacturing.{name}`")
        # 🔒 배포본 파트너 실명 가공(2026-07-18 원칙): 원명 → "협력". 컬럼명·값 모두.
        #    로컬 위키·BigQuery 원천은 원명 유지. (원명은 유니코드 이스케이프 — 공개 repo 노출 방지)
        _raw = "\uc11c\uc9c4"
        df.columns = [c.replace(_raw, "협력").replace("협력사외로딩", "사외협력로딩") for c in df.columns]
        df = df.replace(_raw, "협력", regex=True)
        df.to_csv(DATA / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"  ✔ {name:24} {len(df):>4}행")
    print("=== 제조 파생 스냅샷 (조인·집계 쿼리) ===")
    for name, sql in MFG_Q.items():
        df = q(sql)
        df.to_csv(DATA / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"  ✔ {name:24} {len(df):>4}행")
    # 스냅샷 기준일 스탬프 — 배지에 "몇 월 며칠 기준" 표기용 (DEPLOY 교안 p3·p5: 한계 명시의 코드화)
    import datetime
    (DATA / "_snapshot_date.txt").write_text(datetime.date.today().isoformat(), encoding="utf-8")
    print("\n스냅샷 파이프라인 완료 — BigQuery 원천 기준으로 data/ 재생성됨 (기준일 스탬프 포함)")


if __name__ == "__main__":
    main()
