# 종합실습1. 비동기 ETL 파이프라인
# Extract(실습3 비동기 수집) → Transform(실습2 Pydantic 검증) → Load(CSV/Parquet 저장)
# 포인트: 네트워크/파일 만지는 부분은 가장자리로 밀고, 가운데(transform)는 순수 함수로.
# 그래야 테스트가 된다. (test_pipeline.py 참고)
#
# 실행: python Total1/pipeline.py
# 테스트: cd Total1 && pytest -v

import asyncio
import random
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from models import Product

OUT_DIR = Path(__file__).resolve().parent / "output"

CATEGORIES = [
    "Food",
    " Electronics ",
    "BEAUTY",
    "home",
    " Fashion",
]  # 일부러 지저분하게
REGIONS = ["KR", "US", "JP", "DE"]


# ---------------- Extract ----------------
async def fetch_product(item_id: int, delay: float = 0.05) -> dict:
    """가짜 상품 API. id 기준으로 결정적이라 몇 번 돌려도 같은 데이터가 나온다."""
    await asyncio.sleep(delay)
    rec = {
        "id": item_id,
        "name": f"상품-{item_id:03d}",
        "category": CATEGORIES[item_id % len(CATEGORIES)],
        "price": float(1000 + item_id * 137 % 90000),
        "quantity": item_id * 7 % 300,
        "seller": {
            "seller_id": 100 + item_id % 8,
            "region": REGIONS[item_id % len(REGIONS)],
        },
        "tags": ["sale"] if item_id % 3 == 0 else [],
    }
    # 오염 주입 (현실의 API는 이런 걸 아무렇지 않게 보낸다)
    if item_id % 9 == 4:
        rec["price"] = -rec["price"]  # 음수 가격
    if item_id % 14 == 11:
        rec["quantity"] = "품절임박"  # 숫자 자리에 문자열
    if item_id % 20 == 17:
        rec["seller"]["region"] = "  "  # 중첩 필드 오염
    return rec


async def extract(
    ids: list[int], max_concurrent: int = 10, delay: float = 0.05
) -> list[dict]:
    """비동기 수집. 동시 10개 제한 + 실패시 백오프 재시도 (실습3 구조 그대로)"""
    sem = asyncio.Semaphore(max_concurrent)

    async def one(i: int) -> dict:
        for attempt in range(3):
            try:
                async with sem:
                    # 모의 환경이라 네트워크 장애는 5%만 흉내
                    if delay > 0 and random.random() < 0.05:
                        raise ConnectionError("일시 오류")
                    return await fetch_product(i, delay)
            except ConnectionError:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.2 * 2**attempt)

    results = await asyncio.gather(*[one(i) for i in ids], return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]


# ---------------- Transform ----------------
def transform(raw: list[dict]) -> tuple[list[Product], list[dict]]:
    """검증 + 정규화. 입력만 받고 결과만 돌려주는 순수 함수 (파일/네트워크 안 건드림)"""
    valid, invalid = [], []
    for row in raw:
        try:
            valid.append(Product(**row))
        except ValidationError as e:
            invalid.append({"data": row, "errors": e.errors()})
    return valid, invalid


# ---------------- Load ----------------
def load(valid: list[Product], out_dir: Path = OUT_DIR) -> pd.DataFrame:
    """DataFrame으로 만들어 CSV + Parquet 저장. 중첩 구조는 납작하게 펴서."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for p in valid:
        d = p.model_dump()  # v2 문법. .dict()는 옛날 거
        seller = d.pop("seller")
        d["seller_id"] = seller["seller_id"]
        d["seller_region"] = seller["region"]
        d["tags"] = ",".join(d["tags"])  # CSV에 리스트 그대로 넣으면 지저분해서
        rows.append(d)

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "products.csv", index=False)
    df.to_parquet(out_dir / "products.parquet", index=False)
    return df


# ---------------- Orchestrate ----------------
async def run(ids: list[int]) -> dict:
    # run()은 조율만 한다. 일은 E/T/L이 각자 알아서.
    raw = await extract(ids)
    valid, invalid = transform(raw)
    df = load(valid)
    return {
        "요청": len(ids),
        "수집": len(raw),
        "유효": len(valid),
        "무효": len(invalid),
        "저장행수": len(df),
    }


if __name__ == "__main__":
    random.seed(42)
    summary = asyncio.run(run(list(range(60))))

    print("=" * 44)
    print("  비동기 ETL 파이프라인 실행 결과")
    print("=" * 44)
    for k, v in summary.items():
        print(f"  {k:<6}: {v}")
    print(f"\n산출물 → {OUT_DIR}/products.csv, products.parquet")

    # 뭐가 걸러졌는지도 눈으로 확인 (안 보이면 불안하니까)
    raw = asyncio.run(extract(list(range(60)), delay=0))
    _, invalid = transform(raw)
    print(f"\n[무효 처리된 {len(invalid)}건의 사유]")
    for item in invalid[:6]:
        err = item["errors"][0]
        loc = ".".join(str(x) for x in err["loc"])
        print(f"  id={item['data']['id']:<3} {loc:<15} {err['msg']}")
    if len(invalid) > 6:
        print(f"  ... 외 {len(invalid) - 6}건")
