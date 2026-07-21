# [창의 과제] 고객 이탈 조기경보 · 리텐션 우선순위 시뮬레이터
# ------------------------------------------------------------
# 종합2에서 만든 모델(churn_model.joblib)을 실제로 "배포"해서 써보는 과제.
# 모델을 만드는 것과 쓰는 것은 다르다 — joblib.load로 불러와 이번 달 고객을
# 점수화하고, 단순히 "이탈확률 높은 순"이 아니라
#     기대손실 = 이탈확률 × 월요금
# 으로 우선순위를 매긴다. 확률 0.9인 월 2만원 고객보다, 확률 0.5인 월 12만원
# 고객을 먼저 잡는 게 회사엔 이득이기 때문. (한정된 상담원을 어디에 쓸 것인가)
#
# 실행: python Advanced/churn_early_warning.py

from pathlib import Path

import joblib
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data" / "telco_churn.csv"
MODEL = BASE.parent / "Total2" / "output" / "churn_model.joblib"
OUT = BASE / "output"

NUM_COLS = [
    "tenure_months",
    "monthly_charges",
    "total_charges",
    "num_services",
    "senior",
]
CAT_COLS = ["gender", "contract", "payment_method"]


def load_model():
    # 종합2를 먼저 안 돌렸으면 모델이 없다 → 친절하게 안내
    if not MODEL.exists():
        raise SystemExit(
            f"모델이 없습니다: {MODEL}\n먼저 'python Total2/analysis.py'를 실행해 모델을 만들어주세요."
        )
    return joblib.load(MODEL)  # 전처리까지 통째로 딸려온다 → 새 데이터도 바로 예측


def this_month_customers(n=200, seed=7):
    # 이번 달 계약갱신을 앞둔 고객이라고 가정하고 표본을 뽑는다 (재현성 위해 seed 고정)
    df = pd.read_csv(DATA)
    df["total_charges"] = pd.to_numeric(df["total_charges"], errors="coerce")
    sample = df.sample(n=n, random_state=seed).reset_index(drop=True)
    return sample


def tier(p):
    if p >= 0.6:
        return "🔴 높음"
    if p >= 0.35:
        return "🟡 중간"
    return "🟢 낮음"


def main():
    model = load_model()
    cust = this_month_customers()

    # 이탈확률 예측 → 기대손실 계산 → 우선순위 정렬
    cust["이탈확률"] = model.predict_proba(cust[NUM_COLS + CAT_COLS])[:, 1]
    cust["위험도"] = cust["이탈확률"].map(tier)
    cust["월기대손실"] = (cust["이탈확률"] * cust["monthly_charges"]).round(1)

    ranked = cust.sort_values("월기대손실", ascending=False).reset_index(drop=True)

    print("=" * 62)
    print("  고객 이탈 조기경보 리포트 (이번 달 갱신대상 200명)")
    print("=" * 62)

    dist = cust["위험도"].value_counts()
    for t in ["🔴 높음", "🟡 중간", "🟢 낮음"]:
        print(f"  {t}: {dist.get(t, 0)}명")

    risk_total = cust["월기대손실"].sum()
    high = cust[cust["이탈확률"] >= 0.6]
    # 요금은 합성 데이터라 단위는 상대값(pt)으로 본다. 절대금액이 아니라 '어디에 집중할지'가 핵심.
    print(f"\n월 기대손실 총합: {risk_total:,.0f} pt")
    print(
        f"고위험 고객만 잡아도 방어 가능액: 월 {high['월기대손실'].sum():,.0f} pt "
        f"(전체의 {high['월기대손실'].sum() / risk_total:.0%})"
    )

    # 한정된 상담원이 오늘 전화할 우선순위 TOP 10
    print("\n[오늘 전화할 리텐션 우선순위 TOP 10]")
    print(
        f"  {'고객ID':<12}{'위험도':<8}{'이탈확률':>8}{'월요금':>9}{'월기대손실':>11}  계약"
    )
    print("  " + "-" * 62)
    for _, r in ranked.head(10).iterrows():
        print(
            f"  {r['customer_id']:<12}{r['위험도']:<7}{r['이탈확률']:>7.0%}"
            f"{r['monthly_charges']:>9,.0f}{r['월기대손실']:>11,.0f}  {r['contract']}"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    cols = [
        "customer_id",
        "위험도",
        "이탈확률",
        "monthly_charges",
        "월기대손실",
        "contract",
        "tenure_months",
    ]
    out_path = OUT / "retention_priority.csv"
    ranked[cols].to_csv(
        out_path, index=False, encoding="utf-8-sig"
    )  # 엑셀에서 한글 안 깨지게
    print(f"\n전체 우선순위 목록 저장: {out_path.name} (상담팀 배포용)")
    print(
        "포인트: '확률 높은 순'이 아니라 '기대손실 높은 순'. 고가치 고객을 먼저 지킨다."
    )


if __name__ == "__main__":
    main()
