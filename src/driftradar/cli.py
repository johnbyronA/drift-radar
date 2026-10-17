"""Interfaz de línea de comandos.

Códigos de salida:
  0  sin drift por encima del umbral de falla (``--fail-on``)
  1  se detectó drift/alerta según ``--fail-on``
  2  error de uso o de lectura
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .core import compare
from .io import read_table

_RANK = {"ok": 0, "warning": 1, "drift": 2}


def _split(v: str | None) -> list[str] | None:
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="driftradar",
        description="Detecta drift entre dos versiones de un dataset (CSV, Parquet, JSON, Excel).",
    )
    p.add_argument("--version", action="version", version=f"driftradar {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="Compara un dataset actual contra uno de referencia")
    c.add_argument("reference", help="Archivo de referencia (línea base)")
    c.add_argument("current", help="Archivo actual a evaluar")
    c.add_argument("--html", metavar="RUTA", help="Escribe reporte HTML autocontenido")
    c.add_argument("--json", metavar="RUTA", help="Escribe reporte JSON (máquina)")
    c.add_argument("--markdown", metavar="RUTA", help="Escribe reporte Markdown ($GITHUB_STEP_SUMMARY)")
    c.add_argument("--config", metavar="TOML", help="driftradar.toml o pyproject.toml con [tool.driftradar]")
    c.add_argument("--columns", help="Lista separada por comas de columnas a analizar")
    c.add_argument("--exclude", help="Lista separada por comas de columnas a ignorar")
    c.add_argument("--parse-dates", help="Columnas a interpretar como fecha (separadas por comas)")
    c.add_argument("--sep", help="Separador para CSV (por defecto se autodetecta)")
    c.add_argument("--psi-warning", type=float, help="Umbral PSI de alerta (def. 0.10)")
    c.add_argument("--psi-drift", type=float, help="Umbral PSI de drift (def. 0.25)")
    c.add_argument(
        "--fail-on",
        choices=["drift", "warning", "never"],
        default="drift",
        help="Estado que hace terminar con código 1 (def. drift)",
    )
    c.add_argument("-q", "--quiet", action="store_true", help="No imprime el resumen en consola")

    d = sub.add_parser("demo", help="Genera datos sintéticos y un reporte de ejemplo")
    d.add_argument("--out", default="driftradar-demo", help="Carpeta de salida")
    d.add_argument("--rows", type=int, default=5000)
    d.add_argument("--seed", type=int, default=42)
    return p


def _config_from_args(a: argparse.Namespace) -> Config:
    base = Config.from_toml(a.config).__dict__.copy() if a.config else {}
    overrides = {
        "psi_warning": a.psi_warning,
        "psi_drift": a.psi_drift,
        "columns": _split(a.columns),
        "exclude": _split(a.exclude),
    }
    base.update({k: v for k, v in overrides.items() if v is not None})
    return Config.from_dict(base)


def _print_summary(report) -> None:
    sym = {"ok": "OK  ", "warning": "WARN", "drift": "DRIFT"}
    print(
        f"driftradar {__version__} · {report.rows_ref:,} → {report.rows_cur:,} filas · "
        f"estado global: {report.status.upper()}"
    )
    if report.schema.removed:
        print(f"  columnas eliminadas: {', '.join(report.schema.removed)}")
    if report.schema.added:
        print(f"  columnas nuevas: {', '.join(report.schema.added)}")
    width = max((len(c.name) for c in report.columns), default=10)
    for c in report.columns:
        psi = "  nan" if c.psi != c.psi else f"{c.psi:6.3f}"
        print(f"  [{sym[c.status]:<5}] {c.name:<{width}}  PSI {psi}  {c.kind}")


def _write(path: str, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if path == os.environ.get("GITHUB_STEP_SUMMARY") else "w"
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(text)


def _cmd_compare(a: argparse.Namespace) -> int:
    cfg = _config_from_args(a)
    dates = _split(a.parse_dates)
    ref = read_table(a.reference, sep=a.sep, parse_dates=dates)
    cur = read_table(a.current, sep=a.sep, parse_dates=dates)
    report = compare(ref, cur, cfg, reference_name=Path(a.reference).name, current_name=Path(a.current).name)
    if a.html:
        _write(a.html, report.to_html())
    if a.json:
        _write(a.json, report.to_json())
    if a.markdown:
        _write(a.markdown, report.to_markdown())
    if not a.quiet:
        _print_summary(report)
    if a.fail_on == "never":
        return 0
    return 1 if _RANK[report.status] >= _RANK[a.fail_on] else 0


def _cmd_demo(a: argparse.Namespace) -> int:
    from .datasets import make_demo

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ref, cur = make_demo(n=a.rows, seed=a.seed)
    ref.to_csv(out / "solicitudes_agosto.csv", index=False)
    cur.to_csv(out / "solicitudes_septiembre.csv", index=False)
    report = compare(
        ref,
        cur,
        Config(exclude=["id_solicitud", "fecha"]),
        reference_name="solicitudes_agosto.csv",
        current_name="solicitudes_septiembre.csv",
    )
    _write(str(out / "reporte.html"), report.to_html())
    _write(str(out / "reporte.json"), report.to_json())
    _write(str(out / "reporte.md"), report.to_markdown())
    _print_summary(report)
    print(f"\nArchivos escritos en {out.resolve()}  →  abre reporte.html en tu navegador")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "compare":
            return _cmd_compare(args)
        return _cmd_demo(args)
    except (FileNotFoundError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
