# 종합실습2. EDA + 통계검정 + ML 파이프라인
# 통신사 고객 7천명 데이터로 "이 고객이 이탈할까"를 예측한다.
# 근데 모델만 만드는 게 아니라 분석의 전형적 흐름 전체를 경험하는 게 목적:
#   탐색(EDA) → 시각화 → 통계검정 → 머신러닝
# 이 순서를 지키는 게 절반이다. 바로 모델부터 돌리면 결과를 설명 못 한다.
#
# 실행: python Total2/analysis.py
# 산출물: output/eda_report.html (Plotly), output/churn_model.joblib

from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import polars as pl
from plotly.offline import get_plotlyjs
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data" / "telco_churn.csv"
OUT = BASE / "output"

NUM_COLS = [
    "tenure_months",
    "monthly_charges",
    "total_charges",
    "num_services",
    "senior",
]
CAT_COLS = ["gender", "contract", "payment_method"]


def eda():
    # STEP0~1. Polars로 데이터에 뭐가 있는지부터. 타깃 비율을 가장 먼저 본다.
    df = pl.read_csv(DATA)
    print("=" * 54)
    print("  STEP0. EDA")
    print("=" * 54)
    print(f"shape: {df.shape}")

    churn_rate = df["churn"].mean() * 100
    print(f"이탈률: {churn_rate:.1f}%  (이탈 {df['churn'].sum()} / 전체 {df.height})")
    print("→ 불균형이라 정확도(accuracy)는 못 쓴다. 그래서 ROC-AUC를 지표로.")

    # 이탈 vs 잔류 그룹 비교 (가설 세우기)
    grp = (
        df.group_by("churn")
        .agg(
            pl.col("monthly_charges").mean().round(1).alias("평균요금"),
            pl.col("tenure_months").mean().round(1).alias("평균가입개월"),
            pl.len().alias("인원"),
        )
        .sort("churn")
    )
    print("\n[이탈 여부별 비교]")
    print(grp)
    print(
        "→ 이탈 고객의 요금이 더 높고 가입기간이 짧아 보인다. 진짜일까? STEP2 통계검정으로."
    )
    return df.to_pandas()


def stat_tests(pdf):
    # STEP2. 통계검정 — 눈으로 본 걸 숫자로 확인 (우연일 확률 p값)
    print("\n" + "=" * 54)
    print("  STEP2. 통계 검정")
    print("=" * 54)

    yes = pdf[pdf["churn"] == 1]["monthly_charges"]
    no = pdf[pdf["churn"] == 0]["monthly_charges"]
    t, p_t = stats.ttest_ind(yes, no, equal_var=False)  # Welch t-검정
    print(f"t-검정 (월요금, 이탈 vs 잔류): t={t:.2f}, p={p_t:.2e}")

    table = pd.crosstab(pdf["contract"], pdf["churn"])
    chi2, p_chi, dof, _ = stats.chi2_contingency(table)
    print(f"카이제곱 (계약유형 vs 이탈): chi2={chi2:.1f}, p={p_chi:.2e}")

    sig_t = "유의함" if p_t < 0.05 else "유의하지 않음"
    sig_c = "유의함" if p_chi < 0.05 else "유의하지 않음"
    print(f"→ 둘 다 p<0.05 ({sig_t}, {sig_c}). 단, 연관이지 인과가 아니다.")
    return {"t": t, "p_t": p_t, "chi2": chi2, "p_chi": p_chi}


def build_model(pdf):
    # STEP4~7. 가공 → ColumnTransformer → Pipeline 학습 → 평가
    print("\n" + "=" * 54)
    print("  STEP4~7. 머신러닝 (Pipeline으로 누수 방지)")
    print("=" * 54)

    pdf = pdf.copy()
    pdf["total_charges"] = pd.to_numeric(pdf["total_charges"], errors="coerce")

    X = pdf[NUM_COLS + CAT_COLS]
    y = pdf["churn"].astype(int)

    # 전처리: 숫자는 중앙값대치+표준화, 범주는 One-Hot (순서형 인코딩은 가짜 크기관계를 만든다)
    preprocessor = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="median")),
                        ("sc", StandardScaler()),
                    ]
                ),
                NUM_COLS,
            ),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ]
    )

    # stratify=y : 이탈 비율을 train/test에 동일하게 유지
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipe = Pipeline(
        [
            ("prep", preprocessor),
            ("model", RandomForestClassifier(n_estimators=200, random_state=42)),
        ]
    )
    pipe.fit(X_tr, y_tr)  # 전처리+모델이 train 안에서만 학습됨 → 누수 없음

    # ROC-AUC는 확률(predict_proba)로 계산. 0/1을 넣으면 안 된다.
    proba = pipe.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, proba)
    print(
        f"ROC-AUC = {auc:.3f}  (0.5=동전, 1.0=완벽 / 0.6대는 개선여지 있는 실전 수준)"
    )
    print("\n[classification_report]")
    print(
        classification_report(y_te, pipe.predict(X_te), target_names=["잔류", "이탈"])
    )

    OUT.mkdir(parents=True, exist_ok=True)
    model_path = OUT / "churn_model.joblib"
    # 전처리까지 통째로 저장 → 새 데이터도 바로 예측 가능. compress로 용량 크게 절감
    joblib.dump(pipe, model_path, compress=3)
    print(f"모델 저장: {model_path.name} (전처리 포함 Pipeline 통째로)")

    # 어떤 변수가 예측에 크게 기여했나 (해석 가능성)
    feat_names = pipe.named_steps["prep"].get_feature_names_out()
    importances = pipe.named_steps["model"].feature_importances_
    top = sorted(zip(feat_names, importances), key=lambda x: -x[1])[:5]
    print("중요 변수 TOP5:", [f"{n.split('__')[-1]}({v:.2f})" for n, v in top])
    return auc


def build_report(pdf, stat_result, auc):
    # STEP3(시각화)를 리포트로. Plotly 그림 여러 개를 한 HTML로 묶는다.
    # plotly.js를 head에 한 번만 심고 각 그림은 조각(fragment)으로 붙인다 → 오프라인에서도 열림
    figs = []

    fig1 = px.box(
        pdf,
        x="churn",
        y="monthly_charges",
        color="churn",
        title="① 이탈 여부별 월요금 분포 (박스플롯)",
        labels={"churn": "이탈(1)/잔류(0)", "monthly_charges": "월요금"},
    )
    figs.append(fig1)

    churn_by_contract = (
        pdf.groupby("contract")["churn"].mean().mul(100).round(1).reset_index()
    )
    fig2 = px.bar(
        churn_by_contract,
        x="contract",
        y="churn",
        title="② 계약유형별 이탈률 (%)",
        labels={"contract": "계약유형", "churn": "이탈률(%)"},
        text="churn",
    )
    figs.append(fig2)

    fig3 = px.histogram(
        pdf,
        x="tenure_months",
        color="churn",
        barmode="overlay",
        nbins=36,
        title="③ 가입기간 분포 (이탈/잔류 겹쳐보기)",
        labels={"tenure_months": "가입개월", "churn": "이탈여부"},
    )
    figs.append(fig3)

    fragments = "".join(
        f.to_html(full_html=False, include_plotlyjs=False) for f in figs
    )

    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>고객 이탈 분석 리포트</title>
<script>{get_plotlyjs()}</script>
<style>
  body {{ font-family: -apple-system, 'Malgun Gothic', sans-serif; max-width: 960px;
         margin: 0 auto; padding: 32px; color: #1a1a2e; background: #ffffff; }}
  h1 {{ border-bottom: 3px solid #3a4a7a; padding-bottom: 12px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }}
  .card {{ flex: 1; min-width: 160px; background: #f2f4fb; border-radius: 12px;
          padding: 18px; border-left: 5px solid #3a4a7a; }}
  .card .v {{ font-size: 26px; font-weight: 700; color: #2a3a6a; }}
  .card .k {{ font-size: 13px; color: #666; margin-top: 4px; }}
  .note {{ background: #fff7e6; border-left: 5px solid #e0a020; padding: 12px 16px;
          border-radius: 8px; font-size: 14px; margin: 16px 0; }}
</style></head><body>
<h1>📊 통신사 고객 이탈 분석 리포트</h1>
<p>telco_churn.csv · 7,000명 · EDA → 시각화 → 통계검정 → ML 전 과정</p>
<div class="cards">
  <div class="card"><div class="v">{pdf["churn"].mean() * 100:.1f}%</div><div class="k">전체 이탈률 (불균형)</div></div>
  <div class="card"><div class="v">{stat_result["p_t"]:.1e}</div><div class="k">월요금 t-검정 p값</div></div>
  <div class="card"><div class="v">{stat_result["p_chi"]:.1e}</div><div class="k">계약유형 카이제곱 p값</div></div>
  <div class="card"><div class="v">{auc:.3f}</div><div class="k">RandomForest ROC-AUC</div></div>
</div>
<div class="note">
  <b>해석 주의:</b> 월요금·계약유형이 이탈과 <b>통계적으로 유의한 연관</b>을 보인다(p&lt;0.05).
  다만 이것은 <b>연관이지 인과가 아니다</b> — "요금이 높아서 이탈한다"고 단정하면 안 된다.
</div>
{fragments}
<p style="color:#888;font-size:12px;margin-top:32px">
  자동 생성 리포트 · 재현성을 위해 random_state=42 고정</p>
</body></html>"""

    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "eda_report.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"\n리포트 저장: {report_path.name} (Plotly 그래프 3개 + 요약카드)")


def main():
    pdf = eda()
    stat_result = stat_tests(pdf)
    auc = build_model(pdf)
    build_report(pdf, stat_result, auc)
    print(
        "\n분석 완료. 모델 점수보다 '왜 그 숫자가 나왔는지' 설명할 수 있는 게 중요하다."
    )


if __name__ == "__main__":
    main()
