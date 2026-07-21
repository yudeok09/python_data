# 실습5. Pandas · Polars · DuckDB 성능 비교
# 똑같은 집계를 세 엔진으로 돌리고 시간을 잰다.
# 이 실습의 진짜 목적은 "Polars 짱"이 아니라, 결과가 같음을 증명한 뒤에 성능을 말하는 것.
# 검증 없는 최적화는 최적화가 아니라 버그다.
#
# 질의 정의(세 엔진 공통):
#   amount > 0 인 거래(purchase/refund)만 골라서
#   event_type 별로 묶고, 건수(cnt)와 amount 평균(avg)을 구한 뒤
#   건수 내림차순 정렬
#
# 실행: python practice5/engine_benchmark.py

import time
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl

CSV = Path(__file__).resolve().parent.parent / "data" / "events_large.csv"
CSV_STR = str(CSV)


def run_pandas():
    # 기준선(baseline). 단일 스레드 · 즉시 실행(eager)
    start = time.perf_counter()
    df = pd.read_csv(CSV)
    res = (
        df[df["amount"] > 0]
        .groupby("event_type")
        .agg(cnt=("amount", "count"), avg=("amount", "mean"))
        .sort_values("cnt", ascending=False)
        .reset_index()
    )
    return res, (time.perf_counter() - start) * 1000


def run_polars():
    # scan_csv = "읽겠다고 계획만" (지연). 실제 실행은 collect()에서.
    # 계획 전체를 보고 최적화하므로 필터가 스캔 단계로 내려간다(predicate pushdown)
    start = time.perf_counter()
    res = (
        pl.scan_csv(CSV_STR)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg([pl.len().alias("cnt"), pl.col("amount").mean().alias("avg")])
        .sort("cnt", descending=True)
        .collect()
    )
    return res, (time.perf_counter() - start) * 1000


def run_duckdb():
    # CSV를 DB에 넣지 않고 SQL로 파일을 바로 조회한다
    start = time.perf_counter()
    res = duckdb.sql(
        f"""
        SELECT event_type,
               COUNT(amount) AS cnt,
               AVG(amount)   AS avg
        FROM '{CSV_STR}'
        WHERE amount > 0
        GROUP BY event_type
        ORDER BY cnt DESC
        """
    ).df()
    return res, (time.perf_counter() - start) * 1000


def show_lazy_plan():
    # Lazy가 왜 빠른지 말로만 하면 안 믿기니까 실행계획을 직접 뽑아본다.
    # collect() 대신 explain()을 부르면 Polars가 짠 계획표가 나온다.
    plan = (
        pl.scan_csv(CSV_STR)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg([pl.len().alias("cnt"), pl.col("amount").mean().alias("avg")])
        .sort("cnt", descending=True)
        .explain()
    )
    print("\n[Polars 실행계획] .explain() — 지연 실행이 뭘 최적화했나")
    for line in plan.splitlines():
        print("  " + line)

    pushed = "SELECTION" in plan.upper() or "FILTER" in plan.upper()
    projected = "PROJECT" in plan.upper() or "σ" in plan
    if pushed or projected:
        print("  → 필터/컬럼 선택이 스캔 단계까지 내려갔다(pushdown).")
        print("    파일을 다 읽고 거르는 게 아니라, 읽을 때부터 걸러서 읽는다.")


def best_of(fn, n=3):
    # 첫 실행엔 캐시·초기화 비용이 섞이므로 여러 번 돌려 가장 빠른 값을 쓴다
    best_ms, result = float("inf"), None
    for _ in range(n):
        result, ms = fn()
        best_ms = min(best_ms, ms)
    return result, best_ms


def verify(res_pandas, res_polars, res_duck):
    # ★ 성능보다 이게 먼저. 비교 전에 정렬·타입·컬럼순서를 맞춰야 한다.
    a = res_pandas.sort_values("event_type").reset_index(drop=True)
    b = res_polars.to_pandas().sort_values("event_type").reset_index(drop=True)
    c = res_duck.sort_values("event_type").reset_index(drop=True)
    # cnt 타입은 엔진마다 다르니(check_dtype=False), 평균은 부동소수 오차 허용(atol)
    pd.testing.assert_frame_equal(a, b, check_dtype=False, atol=1e-6)
    pd.testing.assert_frame_equal(a, c, check_dtype=False, atol=1e-6)


def main():
    print("=" * 52)
    print(
        f"  엔진 성능 비교 (events_large.csv, {CSV.stat().st_size / 1024 / 1024:.0f}MB)"
    )
    print("=" * 52)

    res_pandas, t_pandas = best_of(run_pandas)
    res_polars, t_polars = best_of(run_polars)
    res_duck, t_duck = best_of(run_duckdb)

    print("\n집계 결과 (Pandas 기준):")
    print(res_pandas.to_string(index=False))

    # STEP4. 결과 일치 검증 — 이 실습에서 가장 중요한 단계
    try:
        verify(res_pandas, res_polars, res_duck)
        print("\n✅ 세 엔진 결과 완전 일치 (assert_frame_equal 통과)")
    except AssertionError as e:
        print(f"\n❌ 결과 불일치! 성능 비교는 의미 없음:\n{e}")
        return

    # STEP5. 벤치마크 표
    print("\n[벤치마크] best-of-3, 파일읽기~결과까지 전체 측정")
    print(f"{'엔진':<10}{'시간(ms)':>12}{'배속':>10}")
    print("-" * 32)
    base = t_pandas
    for name, t in sorted(
        [("Polars", t_polars), ("DuckDB", t_duck), ("Pandas", t_pandas)],
        key=lambda x: x[1],
    ):
        print(f"{name:<10}{t:>12.0f}{base / t:>9.1f}x")

    show_lazy_plan()

    print(
        "\n빠른 이유는 '더 빨리 일해서'가 아니라 '쓸데없는 일을 안 해서'(pushdown)다."
    )

    # "항상 Polars"가 정답은 아니라서, 고를 때 뭘 보는지도 정리해봤다
    print("\n[엔진 선택 기준]")
    print("  데이터 규모   : 수천 행이면 Pandas가 더 편하다. 손에 익은 게 빠른 길.")
    print("  SQL 친화도    : 팀이 SQL에 익숙하면 DuckDB가 생산적 (파일을 바로 질의)")
    print("  메모리        : 메모리보다 큰 데이터면 Polars scan_* / DuckDB 쪽이 유리")
    print("  생태계        : 시각화·ML 붙이려면 결국 Pandas로 변환해야 할 때가 많다")


if __name__ == "__main__":
    main()
