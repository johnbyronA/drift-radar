"""Reporte Markdown, pensado para el Job Summary de GitHub Actions o comentarios de PR."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import DriftReport

ICON = {"ok": "🟢", "warning": "🟡", "drift": "🔴"}
LABEL = {"ok": "Estable", "warning": "Alerta", "drift": "Drift"}


def _f(x: float | None, nd: int = 3) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def render_markdown(r: DriftReport, max_rows: int = 50) -> str:
    s = r.to_dict()["summary"]
    out = [
        f"## {ICON[r.status]} driftradar · {LABEL[r.status]}",
        "",
        f"**{r.reference_name}** ({r.rows_ref:,} filas) → **{r.current_name}** ({r.rows_cur:,} filas)"
        f" · {s['columns_analyzed']} columnas analizadas",
        "",
        "| 🔴 Drift | 🟡 Alerta | 🟢 Estable | % columnas con drift |",
        "|---:|---:|---:|---:|",
        f"| {s['drift']} | {s['warning']} | {s['ok']} | {s['share_drifted']:.0%} |",
        "",
    ]
    sc = r.schema
    if sc.added or sc.removed or sc.type_changed:
        out.append("### Cambios de esquema")
        if sc.removed:
            out.append(f"- ❌ Columnas eliminadas: `{'`, `'.join(sc.removed)}`")
        if sc.added:
            out.append(f"- ➕ Columnas nuevas: `{'`, `'.join(sc.added)}`")
        for k, (a, b) in sc.type_changed.items():
            out.append(f"- 🔁 `{k}`: {a} → {b}")
        out.append("")
    out += [
        "### Detalle por columna",
        "",
        "| Estado | Columna | Tipo | PSI | Prueba (p) | Nulos ref → act | Notas |",
        "|---|---|---|---:|---|---|---|",
    ]
    for c in r.columns[:max_rows]:
        notes = "; ".join(c.notes).replace("|", "\\|")
        out.append(
            f"| {ICON[c.status]} | `{c.name}` | {c.kind} | {_f(c.psi)} | {c.test} ({_f(c.p_value, 4)}) "
            f"| {c.null_rate_ref:.1%} → {c.null_rate_cur:.1%} | {notes} |"
        )
    if len(r.columns) > max_rows:
        out.append(f"\n_… y {len(r.columns) - max_rows} columnas más (ver reporte HTML)._")
    out += [
        "",
        f"<sub>driftradar v{r.version} · {r.generated_at} · "
        f"umbrales PSI {r.config.psi_warning}/{r.config.psi_drift}</sub>",
        "",
    ]
    return "\n".join(out)
