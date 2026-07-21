# 실습4. Pandas 2.x 데이터 정제
# sales_raw.csv(5천행)는 이름 그대로 raw다. 결측·이상치·음수가격이 섞여있다.
# 진단 → 타입정규화 → 결측처리 → 이상치처리 → 집계(groupby/pivot/merge) 순서로 정리한다.
# 순서를 지키는 게 핵심 (타입 먼저 안 잡으면 결측 개수가 나중에 또 늘어난다)
# 실행: python practice4/clean_sales.py

from pathlib import Path

import pandas as pd

pd.set_option("display.width", 200)  # 콘솔에서 pivot 잘리지 않게
pd.set_option("display.max_columns", None)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sales_raw.csv"


def diagnose(df):
    # STEP0. 치료 전 진단. 어디가 얼마나 더러운지부터 눈으로 본다
    print("=" * 52)
    print("  STEP0. 진단")
    print("=" * 52)
    print(f"shape: {df.shape}")
    print("dtypes:")
    for col, dt in df.dtypes.items():
        print(f"  {col:<12} {dt}")
    print("결측 개수:")
    for col, n in df.isna().sum().items():
        if n:
            print(f"  {col:<12} {n}건")
    print(
        f"unit_price min/max: {df['unit_price'].min():,.0f} ~ {df['unit_price'].max():,.0f}"
    )
    print(f"quantity max: {df['quantity'].max()} (정상은 1~10)")


def normalize_types(df):
    # STEP1. 타입 정규화. 숫자는 숫자로, 날짜는 날짜로.
    # errors='coerce' = 변환 실패한 값은 에러 대신 NaN으로 (실무 최다 사용)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")

    # 음수 가격은 물리적으로 불가능 → 결측으로 돌려서 아래 결측처리에서 대치되게
    neg = (df["unit_price"] < 0).sum()
    df.loc[df["unit_price"] < 0, "unit_price"] = pd.NA
    print(f"\n[타입정규화] 음수가격 {neg}건을 결측으로 전환 (뒤에서 중앙값 대치)")

    # 범주형은 category 타입으로 (메모리 절약 + groupby 속도)
    df["region"] = df["region"].astype("category")
    df["category"] = df["category"].astype("category")
    return df


def fill_missing(df):
    # STEP2. 결측 처리. 0으로 채우면 "공짜 상품"을 창조하는 셈이라 절대 금지.
    # 가격은 같은 카테고리 상품들의 중앙값으로 채운다 (평균은 이상치에 끌려가니 중앙값)
    before = df["unit_price"].isna().sum()
    df["unit_price"] = df.groupby("category", observed=True)["unit_price"].transform(
        lambda s: s.fillna(s.median())
    )
    # region은 범주형이라 중앙값이 없다 → 'Unknown' 범주로
    if "Unknown" not in df["region"].cat.categories:
        df["region"] = df["region"].cat.add_categories(["Unknown"])
    region_na = df["region"].isna().sum()
    df["region"] = df["region"].fillna("Unknown")
    print(f"[결측처리] unit_price {before}건 → 카테고리별 중앙값 대치")
    print(f"[결측처리] region {region_na}건 → 'Unknown' 범주로")
    print(
        f"           처리 후 결측: unit_price {df['unit_price'].isna().sum()}, region {df['region'].isna().sum()}"
    )
    return df


def winsorize(s, k=1.5):
    # IQR 윈저라이징: 극단값을 삭제하지 않고 경계선까지 끌어당긴다 (행은 살리고 왜곡만 제거)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - k * iqr, q3 + k * iqr
    return s.clip(lower=low, upper=high)


def handle_outliers(df):
    # STEP3. 이상치 처리 (quantity 500~2000 같은 값들을 정상 범위로 눌러준다)
    print("\n[이상치처리] IQR 윈저라이징")
    for col in ["quantity", "unit_price"]:
        before_max = df[col].max()
        df[col] = winsorize(df[col])
        print(f"  {col:<12} max {before_max:>12,.0f} → {df[col].max():>12,.0f}")
    return df


def build_amount(df):
    # 매출액 = 수량 × 단가 × (1 - 할인율). 이후 집계의 기준 컬럼.
    df["amount"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(0)
    return df


def aggregate(df):
    print("\n" + "=" * 52)
    print("  집계 결과")
    print("=" * 52)

    # STEP4. groupby.agg — 카테고리별 세로 요약
    summary = (
        df.groupby("category", observed=True)
        .agg(
            건수=("amount", "count"),
            평균가=("unit_price", "mean"),
            중앙값=("unit_price", "median"),
            총매출=("amount", "sum"),
        )
        .round(0)
    )
    print("\n[groupby] 카테고리별 요약")
    print(summary)

    # STEP5. pivot_table — 카테고리 × 지역 교차표
    pivot = df.pivot_table(
        index="category",
        columns="region",
        values="amount",
        aggfunc="sum",
        fill_value=0,
        observed=True,
    ).round(0)
    print("\n[pivot_table] 카테고리 × 지역 총매출")
    print(pivot)

    # STEP6. merge — 카테고리 마스터(담당팀)를 왼쪽 조인
    master = pd.DataFrame(
        {
            "category": ["Electronics", "Fashion", "Home", "Beauty", "Food"],
            "담당팀": ["가전팀", "패션팀", "리빙팀", "뷰티팀", "푸드팀"],
        }
    )
    before = len(df)
    merged = df.merge(master, on="category", how="left")  # how='left' = 왼쪽 전부 유지
    print(f"\n[merge] 담당팀 결합: {before}행 → {len(merged)}행 (행 수 보존 확인)")
    team = (
        merged.groupby("담당팀", observed=True)["amount"]
        .sum()
        .round(0)
        .sort_values(ascending=False)
    )
    print("담당팀별 총매출:")
    print(team)
    return summary


def main():
    # STEP7. Copy-on-Write: pandas 2.x부터 슬라이스는 항상 복사본처럼 동작.
    # 원본을 바꾸려면 체인인덱싱 말고 .loc으로 직접 써야 한다 (이 코드도 전부 .loc 사용)
    df = pd.read_csv(DATA_PATH)

    diagnose(df)
    na_before = df.isna().sum().sum()

    df = normalize_types(df)
    df = fill_missing(df)
    df = handle_outliers(df)
    df = build_amount(df)

    na_after = df[["region", "unit_price", "quantity"]].isna().sum().sum()
    print(f"\n[정제 전후] 결측 {na_before}건 → {na_after}건")

    aggregate(df)
    print("\n정제 완료. 조용히 바뀐 데이터가 가장 위험하니 전후를 전부 출력했다.")


if __name__ == "__main__":
    main()
