# 종합실습3 - pytest (순수 함수라 테스트가 쉽다 — 종합1에서 배운 감각 그대로)
# summarize/render는 파일·시간 안 건드리고 입력→출력만 하니 바로 검증 가능.
# 실행: cd Total3 && pytest -v

from datetime import datetime

import pandas as pd

from 종합실습3_설정 import DEFAULT
from 종합실습3_리포트생성 import render_html, summarize


def sample_df():
    # 카테고리 2개짜리 작은 샘플 (5행에서 되면 5천행에서도 된다)
    return pd.DataFrame(
        {
            "category": ["A", "A", "B", "B", "B"],
            "quantity": [1, 2, 1, 1, 1],
            "unit_price": [100.0, 100.0, 50.0, 50.0, 50.0],
            "discount": [0, 0, 0, 0, 0],
            "amount": [100.0, 200.0, 50.0, 50.0, 50.0],
        }
    )


def test_summarize_총매출_내림차순():
    rows = summarize(sample_df(), group_by="category", top_n=5)
    # A=300, B=150 → A가 먼저
    assert rows[0]["group"] == "A"
    assert rows[0]["total"] == 300
    assert rows[1]["group"] == "B"


def test_summarize_top_n_제한():
    rows = summarize(sample_df(), group_by="category", top_n=1)
    assert len(rows) == 1  # 상위 1개만


def test_건수_집계_정확():
    rows = summarize(sample_df(), group_by="category", top_n=5)
    counts = {r["group"]: r["count"] for r in rows}
    assert counts == {"A": 2, "B": 3}


def test_render_html_템플릿_치환완료():
    rows = summarize(sample_df(), group_by="category", top_n=5)
    html = render_html(DEFAULT, rows, datetime(2026, 7, 22, 9, 0, 0))
    # 미치환 템플릿 태그가 남으면 안 되고, 실제 값이 들어가야 함
    assert "{{" not in html
    assert "2026-07-22" in html
    assert "300" in html  # A 총매출
