# 실습4 확장과제 — 정제 규칙을 함수로 쪼갰으니 테스트를 붙인다.
# 다음 달에 새 데이터가 와도 "내 정제 규칙이 여전히 맞게 도는지" 자동으로 확인 가능.
# 실행: cd practice4 && pytest -v

import pandas as pd
import pytest

from 실습4_데이터_정제 import (
    build_amount,
    fill_missing,
    handle_outliers,
    normalize_types,
    winsorize,
)


@pytest.fixture
def dirty():
    # 실제 sales_raw.csv의 지저분함을 5행으로 축소해서 재현
    return pd.DataFrame(
        {
            "order_id": ["A1", "A2", "A3", "A4", "A5"],
            "order_date": [
                "2025-01-01",
                "2025-01-02",
                "2025-01-03",
                "2025-01-04",
                "2025-01-05",
            ],
            "region": ["Seoul", None, "Busan", "Seoul", None],  # 결측 2건
            "category": ["Food", "Food", "Home", "Home", "Food"],
            "quantity": [1, 2, 3, 4, 900],  # 900은 이상치
            "unit_price": [100.0, None, 300.0, -500.0, 200.0],  # 결측 1 + 음수 1
            "discount": [0, 0, 0.1, 0, 0],
        }
    )


def test_음수가격은_결측으로_전환된다(dirty):
    out = normalize_types(dirty)
    # -500은 물리적으로 불가능한 값이라 결측 처리 대상이 되어야 한다
    assert out["unit_price"].isna().sum() == 2  # 원래 결측 1 + 음수 1


def test_날짜컬럼이_datetime이_된다(dirty):
    out = normalize_types(dirty)
    assert pd.api.types.is_datetime64_any_dtype(out["order_date"])


def test_결측은_카테고리별_중앙값으로_채워진다(dirty):
    out = fill_missing(normalize_types(dirty))
    assert out["unit_price"].isna().sum() == 0
    # Food 그룹의 정상값은 100, 200 → 중앙값 150으로 채워져야 함
    food = out.loc[out["category"] == "Food", "unit_price"]
    assert 150.0 in set(food)


def test_결측지역은_Unknown이_된다(dirty):
    out = fill_missing(normalize_types(dirty))
    assert out["region"].isna().sum() == 0
    assert (out["region"] == "Unknown").sum() == 2


def test_윈저라이징은_행을_안_지우고_경계로_누른다():
    s = pd.Series([1, 2, 3, 4, 5, 900])
    out = winsorize(s)
    assert len(out) == len(s)  # 행 수 유지 (삭제가 아니라 끌어당기기)
    assert out.max() < 900


def test_이상치_처리후_수량이_정상범위로(dirty):
    out = handle_outliers(fill_missing(normalize_types(dirty)))
    assert out["quantity"].max() < 900


def test_매출액은_수량x단가x할인(dirty):
    out = build_amount(handle_outliers(fill_missing(normalize_types(dirty))))
    row = out.iloc[2]  # 3개 × 300원 × (1-0.1) = 810
    assert row["amount"] == pytest.approx(810, abs=1)
