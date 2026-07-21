import asyncio

import pandas as pd

import 창의2_매점_재고관리 as manager


def load_analysis():
    raw = asyncio.run(manager.extract())
    valid, invalid = manager.transform(raw)
    alerts = manager.make_alerts(valid, invalid)
    return valid, invalid, alerts


def test_정상과_오류_상품을_분리한다():
    valid, invalid, _ = load_analysis()
    assert len(valid) == 23
    assert len(invalid) == 3
    assert set(invalid["error_field"]) == {"stock", "price", "product_name"}


def test_품절과_유통기한_경고가_생성된다():
    _, _, alerts = load_analysis()
    alert_ids = set(alerts["alert_id"])
    assert "OUT-P004" in alert_ids
    assert "EXP-P024" in alert_ids
    assert "EXP-P025" in alert_ids


def test_모든_경고에_해결_방향이_있다():
    _, _, alerts = load_analysis()
    assert alerts["action"].str.len().gt(0).all()


def test_결과_파일을_저장한다(tmp_path, monkeypatch):
    valid, invalid, alerts = load_analysis()
    monkeypatch.setattr(manager, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(manager, "make_charts", lambda _: ("차트1", "차트2", "차트3"))

    manager.load(valid, invalid, alerts)

    assert (tmp_path / "cleaned_products.csv").exists()
    assert (tmp_path / "invalid_products.csv").exists()
    assert (tmp_path / "admin_alerts.csv").exists()
    assert (tmp_path / "store_dashboard.html").exists()
    saved = pd.read_csv(tmp_path / "admin_alerts.csv")
    assert len(saved) == len(alerts)
