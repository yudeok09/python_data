# 종합실습3 - 리포트 생성 (관심사 분리: 실제 '일'을 하는 곳)
# 집계 + Jinja2 렌더링만 담당한다. 언제 부를지는 종합실습3_실행_스케줄러.py의 몫.
# HTML을 파이썬 문자열로 조립하면('<td>'+str(x)+...) 금방 지옥이 된다.
# Jinja2는 디자인(템플릿)과 데이터(파이썬)를 분리해준다.

from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from 종합실습3_설정 import DEFAULT, ReportConfig

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _load_and_clean(path: Path) -> pd.DataFrame:
    # 실습4에서 배운 정제를 최소한으로 재사용 (음수·결측 → 카테고리 중앙값)
    df = pd.read_csv(path)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df.loc[df["unit_price"] < 0, "unit_price"] = pd.NA
    df["unit_price"] = df.groupby("category", observed=True)["unit_price"].transform(
        lambda s: s.fillna(s.median())
    )
    df["amount"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(0)
    return df


def summarize(df: pd.DataFrame, group_by: str, top_n: int) -> list[dict]:
    # 설정의 group_by에 따라 카테고리별/지역별 등으로 유연하게 집계
    g = (
        df.groupby(group_by, observed=True)
        .agg(
            count=("amount", "count"),
            avg_price=("unit_price", "mean"),
            total=("amount", "sum"),
        )
        .sort_values("total", ascending=False)
        .head(top_n)
        .reset_index()
    )
    return [
        {
            "group": r[group_by],
            "count": int(r["count"]),
            "avg_price": r["avg_price"],
            "total": r["total"],
        }
        for _, r in g.iterrows()
    ]


def build_kpis(df: pd.DataFrame, rows: list[dict]) -> list[dict]:
    # 표만 있으면 한눈에 안 들어와서 위에 KPI 몇 개를 뽑아둔다.
    grand_total = sum(r["total"] for r in rows)
    order_count = int(df["amount"].count())
    top = max(rows, key=lambda r: r["total"]) if rows else None
    return [
        {"label": "총매출", "value": f"{grand_total:,.0f}"},
        {"label": "주문 건수", "value": f"{order_count:,}"},
        {
            "label": "건당 평균매출",
            "value": f"{grand_total / max(order_count, 1):,.0f}",
        },
        {"label": "매출 1위", "value": top["group"] if top else "-"},
    ]


def render_html(
    config: ReportConfig,
    rows: list[dict],
    generated_at: datetime,
    kpis: list[dict] | None = None,
) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),  # XSS 방지 겸 안전하게
    )
    template = env.get_template("report.html.j2")
    grand_total = sum(r["total"] for r in rows)
    max_total = max((r["total"] for r in rows), default=1) or 1
    return template.render(
        title=config.title,
        group_by=config.group_by,
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        rows=rows,
        row_count=len(rows),
        grand_total=f"{grand_total:,.0f}",
        kpis=kpis or [],
        # 표 안에 비중 막대를 그리려고 1위 대비 비율을 미리 계산해서 넘긴다
        max_total=max_total,
    )


def generate_report(config: ReportConfig = DEFAULT) -> Path:
    # 조율은 안 하고 리포트 하나 만드는 것만. 입력(config) → 출력(파일 경로).
    df = _load_and_clean(config.data_path)
    rows = summarize(df, config.group_by, config.top_n)
    kpis = build_kpis(df, rows)
    now = datetime.now()
    html = render_html(config, rows, now, kpis)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = config.output_dir / f"report_{now:%Y%m%d_%H%M%S}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    # 단독 실행 시 기본 설정으로 리포트 한 번 생성
    path = generate_report()
    print(f"리포트 생성 완료: {path}")
