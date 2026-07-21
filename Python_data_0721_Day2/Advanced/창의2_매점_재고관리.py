# [창의 과제] SKALA 매점 상품관리 대시보드
# 실행: python Advanced/창의2_매점_재고관리.py

import asyncio
import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
from pydantic import BaseModel, ConfigDict, Field, ValidationError

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "skala_store_products.csv"
OUTPUT_DIR = BASE_DIR / "output"


class StoreProduct(BaseModel):
    """매점에 등록할 수 있는 정상 상품의 기준"""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    price: int = Field(gt=0, le=100_000)
    stock: int = Field(ge=0, le=10_000)
    daily_sales: float = Field(ge=0)
    reorder_level: int = Field(ge=0)
    expiry_days: int = Field(ge=0)
    last_price: int = Field(gt=0)
    source: str = Field(min_length=1)


async def fetch_source(source: str, rows: list[dict]) -> list[dict]:
    """매대·창고·공급업체 데이터를 비동기로 가져오는 상황을 모의한다."""
    delays = {"매대": 0.15, "창고": 0.25, "공급업체": 0.35}
    await asyncio.sleep(delays.get(source, 0.1))
    return rows


async def extract() -> list[dict]:
    raw = pd.read_csv(DATA_PATH, keep_default_na=False)

    tasks = []
    for source, group in raw.groupby("source", dropna=False):
        tasks.append(fetch_source(str(source), group.to_dict("records")))

    source_results = await asyncio.gather(*tasks)
    return [row for result in source_results for row in result]


def transform(raw_rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_rows = []
    invalid_rows = []

    for row in raw_rows:
        try:
            product = StoreProduct(**row)
            valid_rows.append(product.model_dump())
        except ValidationError as error:
            first_error = error.errors()[0]
            field = ".".join(str(part) for part in first_error["loc"])
            invalid_rows.append(
                {
                    "product_id": row.get("product_id", "확인 필요"),
                    "product_name": row.get("product_name") or "상품명 누락",
                    "error_field": field,
                    "error_message": first_error["msg"],
                    "recommended_action": data_fix_guide(field),
                }
            )

    valid = pd.DataFrame(valid_rows)
    invalid = pd.DataFrame(invalid_rows)

    valid["inventory_value"] = valid["price"] * valid["stock"]
    valid["price_change_pct"] = (
        (valid["price"] - valid["last_price"]) / valid["last_price"] * 100
    ).round(1)
    valid["days_of_stock"] = valid.apply(
        lambda row: (
            round(row["stock"] / row["daily_sales"], 1)
            if row["daily_sales"] > 0
            else 999.0
        ),
        axis=1,
    )
    return valid, invalid


def data_fix_guide(field: str) -> str:
    guides = {
        "price": "원가표를 확인하고 0원보다 큰 판매가를 다시 입력",
        "stock": "매대와 창고의 실재고를 다시 세어 0 이상으로 수정",
        "product_name": "바코드와 입고표를 확인해 상품명을 입력",
    }
    return guides.get(field, "원본 데이터를 확인한 뒤 올바른 값으로 수정")


def make_alerts(valid: pd.DataFrame, invalid: pd.DataFrame) -> pd.DataFrame:
    alerts = []

    for row in invalid.to_dict("records"):
        alerts.append(
            {
                "alert_id": f"DATA-{row['product_id']}",
                "level": "데이터 오류",
                "product": row["product_name"],
                "reason": f"{row['error_field']}: {row['error_message']}",
                "action": row["recommended_action"],
            }
        )

    for row in valid.to_dict("records"):
        product_id = row["product_id"]
        name = row["product_name"]

        if row["stock"] == 0:
            alerts.append(
                {
                    "alert_id": f"OUT-{product_id}",
                    "level": "긴급",
                    "product": name,
                    "reason": "현재 재고가 0개로 품절 상태",
                    "action": f"오늘 바로 최소 {row['reorder_level'] * 2}개 발주",
                }
            )
        elif row["stock"] <= row["reorder_level"] or row["days_of_stock"] < 2:
            recommended = max(
                row["reorder_level"] * 2 - row["stock"],
                round(row["daily_sales"] * 7 - row["stock"]),
                1,
            )
            alerts.append(
                {
                    "alert_id": f"LOW-{product_id}",
                    "level": "주의",
                    "product": name,
                    "reason": f"재고 {row['stock']}개, 약 {row['days_of_stock']}일분 남음",
                    "action": f"7일 판매분을 고려해 약 {recommended}개 발주",
                }
            )

        if (
            row["expiry_days"] <= 2
            and row["stock"] > row["daily_sales"] * row["expiry_days"]
        ):
            alerts.append(
                {
                    "alert_id": f"EXP-{product_id}",
                    "level": "긴급",
                    "product": name,
                    "reason": f"유통기한 {row['expiry_days']}일, 남은 재고 {row['stock']}개",
                    "action": "마감 할인·1+1 행사 후 남은 수량은 폐기 기준 확인",
                }
            )

        if abs(row["price_change_pct"]) >= 20:
            alerts.append(
                {
                    "alert_id": f"PRICE-{product_id}",
                    "level": "확인",
                    "product": name,
                    "reason": f"이전 가격보다 {row['price_change_pct']:+.1f}% 변동",
                    "action": "입고가와 가격표를 대조하고 오입력이면 판매가 수정",
                }
            )

        if row["daily_sales"] == 0 and row["stock"] > 0:
            alerts.append(
                {
                    "alert_id": f"NOSALE-{product_id}",
                    "level": "관심",
                    "product": name,
                    "reason": f"판매 0개인데 재고가 {row['stock']}개 남음",
                    "action": "진열 위치 변경 또는 묶음 할인 후 추가 발주 보류",
                }
            )
        elif row["days_of_stock"] >= 30:
            alerts.append(
                {
                    "alert_id": f"OVER-{product_id}",
                    "level": "관심",
                    "product": name,
                    "reason": f"현재 판매 속도 기준 약 {row['days_of_stock']}일분 재고",
                    "action": "추가 발주를 보류하고 행사 상품으로 우선 판매",
                }
            )

    order = {"데이터 오류": 0, "긴급": 1, "주의": 2, "확인": 3, "관심": 4}
    result = pd.DataFrame(alerts)
    result["sort_order"] = result["level"].map(order)
    return result.sort_values(["sort_order", "product"]).drop(columns="sort_order")


def make_charts(valid: pd.DataFrame) -> tuple[str, str, str]:
    stock = valid.sort_values("stock", ascending=True)
    fig_stock = px.bar(
        stock,
        x="stock",
        y="product_name",
        color="category",
        orientation="h",
        title="상품별 현재 재고",
        labels={"stock": "재고 수량", "product_name": "상품", "category": "분류"},
    )
    fig_stock.update_layout(height=720, margin=dict(l=20, r=20, t=60, b=20))

    category = valid.groupby("category", as_index=False)["inventory_value"].sum()
    fig_value = px.pie(
        category,
        values="inventory_value",
        names="category",
        hole=0.45,
        title="카테고리별 재고 금액",
    )
    fig_value.update_traces(textposition="inside", textinfo="percent+label")

    fig_sales = px.scatter(
        valid,
        x="daily_sales",
        y="stock",
        size="inventory_value",
        color="category",
        hover_name="product_name",
        title="일평균 판매량과 재고 비교",
        labels={
            "daily_sales": "일평균 판매량",
            "stock": "현재 재고",
            "category": "분류",
        },
    )
    fig_sales.update_layout(height=480)

    return (
        pio.to_html(fig_stock, full_html=False, include_plotlyjs=True),
        pio.to_html(fig_value, full_html=False, include_plotlyjs=False),
        pio.to_html(fig_sales, full_html=False, include_plotlyjs=False),
    )


def alert_table(alerts: pd.DataFrame) -> str:
    rows = []
    level_classes = {
        "데이터 오류": "data-error",
        "긴급": "urgent",
        "주의": "warning",
        "확인": "check",
        "관심": "watch",
    }
    for row in alerts.to_dict("records"):
        alert_id = html.escape(str(row["alert_id"]))
        level = html.escape(str(row["level"]))
        level_class = level_classes[str(row["level"])]
        rows.append(
            "<tr>"
            f'<td><input class="resolve-check" type="checkbox" data-alert="{alert_id}" '
            f'aria-label="{alert_id} 처리 완료"></td>'
            f'<td><span class="level level-{level_class}">{level}</span></td>'
            f"<td>{html.escape(str(row['product']))}</td>"
            f"<td>{html.escape(str(row['reason']))}</td>"
            f"<td>{html.escape(str(row['action']))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_dashboard(
    valid: pd.DataFrame, invalid: pd.DataFrame, alerts: pd.DataFrame
) -> str:
    stock_chart, value_chart, sales_chart = make_charts(valid)
    inventory_value = int(valid["inventory_value"].sum())
    quality_score = len(valid) / (len(valid) + len(invalid)) * 100
    urgent_count = int(alerts["level"].isin(["데이터 오류", "긴급"]).sum())

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SKALA 매점 상품관리 대시보드</title>
  <style>
    :root {{ --navy:#172554; --blue:#2563eb; --bg:#f3f6fb; --card:#ffffff; --text:#172033; --muted:#637083; --line:#dbe3ee; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif; background:var(--bg); color:var(--text); }}
    header {{ background:linear-gradient(135deg,var(--navy),var(--blue)); color:white; padding:30px 5vw; }}
    header h1 {{ margin:0 0 8px; font-size:30px; }}
    header p {{ margin:0; opacity:.86; }}
    main {{ width:min(1400px,92vw); margin:24px auto 50px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:0 5px 18px rgba(23,37,84,.05); }}
    .kpi-label {{ color:var(--muted); font-size:14px; }}
    .kpi-value {{ margin-top:8px; font-size:30px; font-weight:700; }}
    .danger {{ color:#b42318; }}
    .section-title {{ margin:32px 0 12px; font-size:22px; }}
    .charts {{ display:grid; grid-template-columns:1.45fr 1fr; gap:16px; }}
    .wide {{ margin-top:16px; }}
    .table-wrap {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; background:white; }}
    th,td {{ padding:12px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background:#f8fafc; color:#41506a; white-space:nowrap; }}
    tr.resolved td {{ color:#8a94a5; text-decoration:line-through; background:#f8fafc; }}
    .level {{ display:inline-block; min-width:66px; padding:4px 8px; border-radius:999px; text-align:center; font-size:13px; font-weight:700; }}
    .level-data-error,.level-urgent {{ background:#fee4e2; color:#b42318; }}
    .level-warning {{ background:#fff1c2; color:#915907; }}
    .level-check {{ background:#dbeafe; color:#1d4ed8; }}
    .level-watch {{ background:#e8eef5; color:#475467; }}
    .note {{ margin-top:12px; color:var(--muted); font-size:13px; }}
    @media (max-width:900px) {{ .kpis,.charts {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:620px) {{ .kpis,.charts {{ grid-template-columns:1fr; }} header h1 {{ font-size:24px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>SKALA 매점 상품관리 대시보드</h1>
    <p>매대·창고·공급업체 데이터를 모아 재고 위험과 데이터 오류를 한눈에 확인합니다.</p>
  </header>
  <main>
    <section class="kpis" aria-label="핵심 지표">
      <div class="card"><div class="kpi-label">검증 통과 상품</div><div class="kpi-value">{len(valid)}개</div></div>
      <div class="card"><div class="kpi-label">총 재고 금액</div><div class="kpi-value">{inventory_value:,}원</div></div>
      <div class="card"><div class="kpi-label">긴급·데이터 오류</div><div class="kpi-value danger">{urgent_count}건</div></div>
      <div class="card"><div class="kpi-label">데이터 품질 점수</div><div class="kpi-value">{quality_score:.1f}점</div></div>
    </section>

    <h2 class="section-title">재고 현황</h2>
    <section class="charts">
      <div class="card">{stock_chart}</div>
      <div class="card">{value_chart}</div>
    </section>
    <section class="card wide">{sales_chart}</section>

    <h2 class="section-title">관리자 경고 및 권장 조치</h2>
    <section class="card table-wrap">
      <table>
        <thead><tr><th>완료</th><th>등급</th><th>상품</th><th>발견한 문제</th><th>해결 방향</th></tr></thead>
        <tbody>{alert_table(alerts)}</tbody>
      </table>
      <p class="note">완료 체크 상태는 이 브라우저에 자동 저장됩니다.</p>
    </section>
  </main>
  <script>
    const checks = document.querySelectorAll('.resolve-check');
    checks.forEach((check) => {{
      const key = 'skala-store-' + check.dataset.alert;
      check.checked = localStorage.getItem(key) === 'done';
      check.closest('tr').classList.toggle('resolved', check.checked);
      check.addEventListener('change', () => {{
        check.closest('tr').classList.toggle('resolved', check.checked);
        if (check.checked) localStorage.setItem(key, 'done');
        else localStorage.removeItem(key);
      }});
    }});
  </script>
</body>
</html>"""


def load(valid: pd.DataFrame, invalid: pd.DataFrame, alerts: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    valid.to_csv(OUTPUT_DIR / "cleaned_products.csv", index=False, encoding="utf-8-sig")
    invalid.to_csv(
        OUTPUT_DIR / "invalid_products.csv", index=False, encoding="utf-8-sig"
    )
    alerts.to_csv(OUTPUT_DIR / "admin_alerts.csv", index=False, encoding="utf-8-sig")
    dashboard = build_dashboard(valid, invalid, alerts)
    (OUTPUT_DIR / "store_dashboard.html").write_text(dashboard, encoding="utf-8")


async def run() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = await extract()
    valid, invalid = transform(raw)
    alerts = make_alerts(valid, invalid)
    load(valid, invalid, alerts)
    return valid, invalid, alerts


if __name__ == "__main__":
    valid_df, invalid_df, alerts_df = asyncio.run(run())

    print("=" * 58)
    print("  SKALA 매점 상품관리 분석 완료")
    print("=" * 58)
    print(f"전체 상품: {len(valid_df) + len(invalid_df)}개")
    print(f"정상 상품: {len(valid_df)}개 / 데이터 오류: {len(invalid_df)}개")
    print(f"관리자 경고: {len(alerts_df)}건")
    print(
        f"긴급·데이터 오류: {alerts_df['level'].isin(['긴급', '데이터 오류']).sum()}건"
    )
    print("\n[우선 확인할 항목]")
    for row in alerts_df.head(6).to_dict("records"):
        print(f"- [{row['level']}] {row['product']}: {row['reason']}")
        print(f"  → {row['action']}")
    print(f"\n대시보드: {OUTPUT_DIR / 'store_dashboard.html'}")
    print(f"경고 목록: {OUTPUT_DIR / 'admin_alerts.csv'}")
