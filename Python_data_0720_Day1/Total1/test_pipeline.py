# 종합실습1 - pytest 테스트 6개
# 함수 하나 만들면 테스트 하나. E/T/L 각 단계를 따로 검증한다.
# 실행: cd Total1 && pytest -v

import asyncio

import pandas as pd

from pipeline import extract, load, transform


def make_row(**kwargs):
    # 정상 레코드 하나 만들고 필요한 부분만 덮어쓰기 (테스트마다 복붙 안 하려고)
    base = {
        "id": 1,
        "name": "테스트상품",
        "category": "food",
        "price": 1000.0,
        "quantity": 5,
        "seller": {"seller_id": 101, "region": "KR"},
        "tags": [],
    }
    base.update(kwargs)
    return base


def test_카테고리_정규화():
    # " FOOD " 처럼 들어와도 "food"로 통일되는지
    valid, _ = transform([make_row(category=" FOOD ")])
    assert valid[0].category == "food"


def test_음수_가격_거부():
    valid, invalid = transform([make_row(price=-5000)])
    assert len(valid) == 0
    assert len(invalid) == 1
    assert invalid[0]["errors"][0]["loc"] == ("price",)


def test_유효_무효_합계_일치():
    # 한 건도 안 새는지. 검증에서 레코드가 증발하면 최악이다
    rows = [make_row(id=i) for i in range(5)]
    rows.append(make_row(id=99, quantity="많음"))  # 오염 1건
    valid, invalid = transform(rows)
    assert len(valid) + len(invalid) == len(rows)
    assert len(invalid) == 1


def test_extract_결정적_수집(monkeypatch):
    # 같은 ids를 주면 항상 같은 개수·같은 내용이 와야 한다 (재현성)
    import random

    random.seed(0)
    a = asyncio.run(extract(list(range(20)), delay=0))
    random.seed(0)
    b = asyncio.run(extract(list(range(20)), delay=0))
    assert len(a) == 20
    assert a == b


def test_load가_파일을_만든다(tmp_path):
    # 실제 output 폴더 더럽히지 않게 pytest 임시폴더 사용
    valid, _ = transform([make_row(id=i) for i in range(3)])
    df = load(valid, out_dir=tmp_path)
    assert (tmp_path / "products.csv").exists()
    assert (tmp_path / "products.parquet").exists()
    assert len(df) == 3


def test_parquet_라운드트립(tmp_path):
    # 저장했다 다시 읽어도 값/타입이 그대로인지 (CSV는 타입이 다 날아가지만 Parquet은 보존)
    df = pd.DataFrame({"id": [1, 2], "price": [10.5, 20.0], "name": ["a", "b"]})
    p = tmp_path / "t.parquet"
    df.to_parquet(p, index=False)
    back = pd.read_parquet(p)
    pd.testing.assert_frame_equal(df, back)
