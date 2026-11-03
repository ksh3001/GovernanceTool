import pytest

from core.config import ROOT
from core.models import AppRecord
from core.packs import discover_packs
from core.store import Store


def test_create_list_roundtrip(tmp_path):
    store = Store(tmp_path)
    a = store.create_app("HR CV Screener", created_by="asha")
    b = store.create_app("HR CV Screener")
    assert a.app_id == "hr-cv-screener" and b.app_id == "hr-cv-screener-2"
    assert [x.app_id for x in store.list_apps()] == ["hr-cv-screener", "hr-cv-screener-2"]
    assert store.get_app("hr-cv-screener").created_by == "asha"


def test_missing_returns_none(tmp_path):
    assert Store(tmp_path).load("nope", "app.json", AppRecord) is None


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        Store(tmp_path).app_dir("../evil")


def test_discover_packs_includes_coming_soon():
    packs = {p.id: p for p in discover_packs(ROOT / "control_packs")}
    assert packs["eu_ai_act"].available and packs["eu_ai_act"].has_tiers
    assert not packs["iso_42001"].available
