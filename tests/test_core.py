import json

import numpy as np
import pandas as pd
import pytest

import driftradar
from driftradar import Config, compare


def test_no_drift_on_same_distribution(demo_stable):
    ref, cur = demo_stable
    rep = compare(ref, cur, Config(exclude=["id_solicitud"]))
    assert rep.status in ("ok", "warning")
    assert rep.drifted_columns == []


def test_detects_injected_drift(demo):
    ref, cur = demo
    rep = compare(ref, cur, Config(exclude=["id_solicitud", "fecha"]))
    assert rep.status == "drift"
    assert "canal" in rep.drifted_columns
    by = {c.name: c for c in rep.columns}
    assert by["ingreso_mensual"].status in ("warning", "drift")
    assert any("Tasa de nulos" in n for n in by["email_dominio"].notes)
    assert any("nueva" in n for n in by["canal"].notes)
    assert by["edad"].kind == "numeric"
    assert by["plazo_meses"].kind == "categorical"
    assert by["tiene_vivienda"].kind == "categorical"


def test_results_sorted_by_severity(demo):
    rep = compare(*demo)
    ranks = [{"drift": 2, "warning": 1, "ok": 0}[c.status] for c in rep.columns]
    assert ranks == sorted(ranks, reverse=True)


def test_schema_changes(simple_frames):
    ref, cur = simple_frames
    cur = cur.drop(columns=["cat"]).assign(nueva=1)
    rep = compare(ref, cur)
    assert rep.schema.removed == ["cat"]
    assert rep.schema.added == ["nueva"]
    assert rep.status == "drift"


def test_type_change_detected(rng):
    ref = pd.DataFrame({"v": rng.normal(size=500)})
    cur = pd.DataFrame({"v": rng.normal(size=500).round(2).astype(str)})
    cur.loc[:50, "v"] = "N/A"
    rep = compare(ref, cur)
    assert "v" in rep.schema.type_changed


def test_columns_and_exclude(simple_frames):
    ref, cur = simple_frames
    assert [c.name for c in compare(ref, cur, Config(columns=["x"])).columns] == ["x"]
    assert [c.name for c in compare(ref, cur, Config(exclude=["x"])).columns] == ["cat"]
    with pytest.raises(ValueError, match="no existen"):
        compare(ref, cur, Config(columns=["zzz"]))


def test_input_validation(simple_frames):
    ref, _ = simple_frames
    with pytest.raises(TypeError):
        compare(ref, [1, 2, 3])
    with pytest.raises(ValueError):
        compare(pd.DataFrame(), ref)


def test_empty_current_column_is_flagged():
    ref = pd.DataFrame({"x": np.arange(100.0)})
    cur = pd.DataFrame({"x": [np.nan] * 100})
    rep = compare(ref, cur)
    assert rep.columns[0].status == "warning"


def test_datetime_columns(rng):
    base = pd.Timestamp("2026-01-01")
    ref = pd.DataFrame({"d": base + pd.to_timedelta(rng.integers(0, 30, 500), unit="D")})
    cur = pd.DataFrame({"d": base + pd.to_timedelta(rng.integers(60, 90, 500), unit="D")})
    col = compare(ref, cur).columns[0]
    assert col.kind == "datetime" and col.status == "drift"
    assert col.summary_ref["min"].startswith("2026-01")


def test_out_of_range_note(rng):
    ref = pd.DataFrame({"x": rng.uniform(0, 1, 1000)})
    cur = pd.DataFrame({"x": rng.uniform(0.5, 1.5, 1000)})
    assert any("fuera del rango" in n for n in compare(ref, cur).columns[0].notes)


def test_exports(demo):
    rep = compare(*demo)
    d = json.loads(rep.to_json())
    assert d["status"] == rep.status
    assert d["summary"]["columns_analyzed"] == len(rep.columns)
    assert "histogram" not in d["columns"][0]
    assert "histogram" in rep.to_dict(include_histograms=True)["columns"][0]
    df = rep.to_frame()
    assert list(df.columns)[:3] == ["columna", "tipo", "estado"]
    assert df["psi"].is_monotonic_decreasing


def test_config_validation(tmp_path):
    with pytest.raises(ValueError):
        Config(psi_warning=0.3, psi_drift=0.2)
    with pytest.raises(ValueError):
        Config(p_value=2)
    with pytest.raises(ValueError):
        Config(bins=1)
    with pytest.raises(ValueError, match="desconocidas"):
        Config.from_dict({"foo": 1})
    f = tmp_path / "pyproject.toml"
    f.write_text("[tool.driftradar]\npsi_drift = 0.3\nexclude = ['id']\n")
    cfg = Config.from_toml(f)
    assert cfg.psi_drift == 0.3 and cfg.exclude == ["id"]
    g = tmp_path / "driftradar.toml"
    g.write_text("bins = 5\n")
    assert Config.from_toml(g).bins == 5


def test_public_api():
    assert driftradar.__version__
    assert callable(driftradar.compare) and callable(driftradar.read_table)
