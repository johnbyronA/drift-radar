import json

import pytest

from driftradar import Config, compare, read_table
from driftradar.cli import main


def test_html_report_is_self_contained(demo):
    html = compare(*demo, Config(exclude=["id_solicitud"])).to_html()
    assert html.startswith("<!doctype html>")
    assert "<svg" in html and "Reporte de drift" in html
    assert "http://" not in html and "https://" not in html  # sin recursos externos
    assert 'id="driftradar-data"' in html


def test_html_escapes_names():
    import pandas as pd

    ref = pd.DataFrame({"<script>x": ["a", "b"] * 50})
    html = compare(ref, ref).to_html()
    assert "<script>x" not in html.split('id="driftradar-data"')[0]


def test_markdown_report(demo):
    md = compare(*demo).to_markdown()
    assert md.startswith("## ")
    assert "| Estado | Columna |" in md


def test_markdown_schema_and_truncation(simple_frames):
    from driftradar.report.markdown import render_markdown

    ref, cur = simple_frames
    rep = compare(ref, cur.drop(columns=["cat"]).assign(z=1))
    md = render_markdown(rep, max_rows=0)
    assert "Columnas eliminadas" in md and "Columnas nuevas" in md and "columnas más" in md


@pytest.mark.parametrize("ext", ["csv", "tsv", "parquet", "json", "jsonl"])
def test_read_table_formats(tmp_path, simple_frames, ext):
    df = simple_frames[0]
    p = tmp_path / f"d.{ext}"
    if ext == "csv":
        df.to_csv(p, index=False, sep=";")
    elif ext == "tsv":
        df.to_csv(p, index=False, sep="\t")
    elif ext == "parquet":
        df.to_parquet(p)
    elif ext == "json":
        df.to_json(p, orient="records")
    else:
        df.to_json(p, orient="records", lines=True)
    out = read_table(p)
    assert list(out.columns) == ["x", "cat"] and len(out) == len(df)


def test_read_table_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_table(tmp_path / "nope.csv")
    bad = tmp_path / "x.foo"
    bad.write_text("a")
    with pytest.raises(ValueError, match="no soportada"):
        read_table(bad)


def test_read_table_parse_dates(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text('{"f": "2026-01-01"}\n{"f": "2026-02-01"}\n')
    assert str(read_table(p, parse_dates=["f"])["f"].dtype).startswith("datetime64")


def test_cli_demo_and_compare(tmp_path, capsys):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out), "--rows", "800"]) == 0
    ref, cur = out / "solicitudes_agosto.csv", out / "solicitudes_septiembre.csv"
    assert (out / "reporte.html").exists()

    html, js, md = tmp_path / "r.html", tmp_path / "r.json", tmp_path / "r.md"
    code = main(
        [
            "compare",
            str(ref),
            str(cur),
            "--html",
            str(html),
            "--json",
            str(js),
            "--markdown",
            str(md),
            "--exclude",
            "id_solicitud,fecha",
            "--parse-dates",
            "fecha",
        ]
    )
    assert code == 1  # hay drift en el demo
    assert json.loads(js.read_text())["status"] == "drift"
    assert html.read_text().startswith("<!doctype html>")
    assert "estado global: DRIFT" in capsys.readouterr().out

    assert main(["compare", str(ref), str(ref), "-q", "--exclude", "id_solicitud"]) == 0
    assert main(["compare", str(ref), str(cur), "-q", "--fail-on", "never"]) == 0
    assert (
        main(
            [
                "compare",
                str(ref),
                str(cur),
                "-q",
                "--columns",
                "edad",
                "--psi-warning",
                "0.5",
                "--psi-drift",
                "0.9",
            ]
        )
        == 0
    )


def test_cli_config_and_errors(tmp_path, simple_frames, capsys, monkeypatch):
    ref, cur = simple_frames
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    ref.to_csv(a, index=False)
    cur.to_csv(b, index=False)
    cfg = tmp_path / "driftradar.toml"
    cfg.write_text("psi_warning = 0.05\npsi_drift = 0.5\n")
    summary = tmp_path / "summary.md"
    summary.write_text("previo\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert (
        main(
            [
                "compare",
                str(a),
                str(b),
                "--config",
                str(cfg),
                "--markdown",
                str(summary),
                "--fail-on",
                "warning",
                "-q",
            ]
        )
        == 0
    )
    assert summary.read_text().startswith("previo")  # se agrega, no se sobrescribe
    assert main(["compare", str(a), str(tmp_path / "missing.csv")]) == 2
    assert "error:" in capsys.readouterr().err
