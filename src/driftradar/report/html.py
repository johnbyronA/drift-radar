"""Reporte HTML autocontenido: un solo archivo, sin dependencias externas ni JS de terceros."""

from __future__ import annotations

import json
import math
from html import escape
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core import ColumnResult, DriftReport

LABEL = {"ok": "Estable", "warning": "Alerta", "drift": "Drift"}
ICON = {"ok": "●", "warning": "▲", "drift": "■"}


def _f(x: Any, nd: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if isinstance(x, float):
        if abs(x) >= 1000:
            return f"{x:,.0f}"
        return f"{x:.{nd}f}"
    return escape(str(x))


def _pct(x: float) -> str:
    return f"{x:.1%}"


# --------------------------------------------------------------------- charts
def _svg_numeric(h: dict) -> str:
    ref, cur, edges = h["ref"], h["cur"], h["edges"]
    n = len(ref)
    W, H, pl, pb, pt = 560, 170, 8, 26, 10
    iw, ih = W - 2 * pl, H - pb - pt
    vmax = max(max(ref), max(cur), 1e-9)
    slot = iw / n
    bw = max((slot - 4) / 2, 1)
    parts = [
        f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Histograma referencia vs actual">'
    ]
    for g in (0.5, 1.0):
        y = pt + ih - ih * g
        parts.append(f'<line x1="{pl}" x2="{W - pl}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
    for i in range(n):
        x0 = pl + i * slot + 1
        for j, (vals, cls) in enumerate(((ref, "s-ref"), (cur, "s-cur"))):
            v = vals[i]
            bh = ih * v / vmax
            x = x0 + j * (bw + 2)
            y = pt + ih - bh
            r = min(4, bw / 2, bh) if bh > 0 else 0
            tip = f"{'Referencia' if j == 0 else 'Actual'} · [{edges[i]} – {edges[i + 1]}): {v:.1%}"
            parts.append(
                f'<g class="mark"><rect x="{x - 1:.1f}" y="{pt}" width="{bw + 2:.1f}" height="{ih}" '
                f'class="hit"/><path class="{cls}" d="{_bar_path(x, y, bw, bh, r)}"/>'
                f"<title>{escape(tip)}</title></g>"
            )
    parts.append(f'<line x1="{pl}" x2="{W - pl}" y1="{pt + ih}" y2="{pt + ih}" class="axis"/>')
    for i in (0, n // 2, n):
        x = pl + i * slot
        anchor = "start" if i == 0 else "end" if i == n else "middle"
        parts.append(
            f'<text x="{x:.1f}" y="{H - 8}" text-anchor="{anchor}" class="tick">{escape(edges[i])}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _bar_path(x: float, y: float, w: float, h: float, r: float) -> str:
    """Barra con esquinas superiores redondeadas, anclada a la línea base."""
    if h <= 0:
        return ""
    b = y + h
    return (
        f"M{x:.1f},{b:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
        f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{b:.1f}Z"
    )


def _svg_categorical(h: dict) -> str:
    labels, ref, cur = h["labels"], h["ref"], h["cur"]
    n = len(labels)
    row, lw, W, pr = 26, 130, 560, 52
    H = n * row + 6
    iw = W - lw - pr
    vmax = max(max(ref, default=0), max(cur, default=0), 1e-9)
    parts = [
        f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" '
        f'aria-label="Frecuencias por categoría referencia vs actual">'
    ]
    for i, lab in enumerate(labels):
        y0 = 3 + i * row
        short = lab if len(lab) <= 18 else lab[:17] + "…"
        parts.append(
            f'<text x="{lw - 8}" y="{y0 + 15}" text-anchor="end" class="lab">'
            f"{escape(short)}<title>{escape(lab)}</title></text>"
        )
        for j, (vals, cls) in enumerate(((ref, "s-ref"), (cur, "s-cur"))):
            v = vals[i]
            bw = iw * v / vmax
            y = y0 + 2 + j * 11
            tip = f"{lab} · {'Referencia' if j == 0 else 'Actual'}: {v:.1%}"
            parts.append(
                f'<g class="mark"><rect x="{lw}" y="{y - 1}" width="{iw + pr}" height="11" class="hit"/>'
                f'<rect x="{lw}" y="{y}" width="{max(bw, 0):.1f}" height="9" rx="2" class="{cls}"/>'
                f"<title>{escape(tip)}</title></g>"
            )
        delta = cur[i] - ref[i]
        parts.append(f'<text x="{W - 4}" y="{y0 + 15}" text-anchor="end" class="tick">{delta:+.1%}</text>')
    parts.append(f'<line x1="{lw}" x2="{lw}" y1="0" y2="{H}" class="axis"/></svg>')
    return "".join(parts)


# ---------------------------------------------------------------------- cards
def _summary_table(c: ColumnResult) -> str:
    keys = list(dict.fromkeys([*c.summary_ref, *c.summary_cur]))
    if not keys:
        return ""
    rows = "".join(
        f"<tr><th>{escape(k)}</th><td>{_fmt_summary(k, c.summary_ref.get(k))}</td>"
        f"<td>{_fmt_summary(k, c.summary_cur.get(k))}</td></tr>"
        for k in keys
    )
    return (
        f'<table class="mini"><thead><tr><th></th><th>Referencia</th><th>Actual</th></tr>'
        f"</thead><tbody>{rows}</tbody></table>"
    )


def _fmt_summary(k: str, v: Any) -> str:
    if k == "top_pct" and isinstance(v, float):
        return _pct(v)
    return _f(v, 2)


def _card(c: ColumnResult) -> str:
    h = c.histogram
    chart = ""
    if h.get("type") == "numeric":
        chart = _svg_numeric(h)
    elif h.get("type") == "categorical" and h.get("labels"):
        chart = _svg_categorical(h)
    notes = "".join(f"<li>{escape(n)}</li>" for n in c.notes)
    test_name = "KS" if c.test == "ks" else "χ²"
    wass = (
        f"<div><span>Wasserstein/σ</span><b>{_f(c.wasserstein)}</b></div>"
        if c.wasserstein is not None
        else ""
    )
    return f"""
<article class="card" data-status="{c.status}" data-name="{escape(c.name.lower())}" id="col-{escape(c.name)}">
  <header>
    <h3>{escape(c.name)} <small>{c.kind}</small></h3>
    <span class="badge b-{c.status}">{ICON[c.status]} {LABEL[c.status]}</span>
  </header>
  <div class="kpis">
    <div><span>PSI</span><b>{_f(c.psi)}</b></div>
    <div><span>{test_name} p-valor</span><b>{_f(c.p_value, 4)}</b></div>
    {wass}
    <div><span>Nulos</span><b>{_pct(c.null_rate_ref)} → {_pct(c.null_rate_cur)}</b></div>
  </div>
  {'<ul class="notes">' + notes + "</ul>" if notes else ""}
  <div class="body">
    <figure>{chart}</figure>
    {_summary_table(c)}
  </div>
</article>"""


# ---------------------------------------------------------------------- page
CSS = """
:root{color-scheme:light;--bg:#f4f4f2;--surface:#fcfcfb;--line:#e4e3df;--text:#0b0b0b;
--text2:#52514e;--muted:#7a7974;--ref:#2a78d6;--cur:#eb6834;--good:#0ca30c;--warn:#b07a00;
--crit:#d03b3b;--accent:#2a78d6}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){color-scheme:dark;
--bg:#111110;--surface:#1a1a19;--line:#2e2e2c;--text:#f0efec;--text2:#c3c2b7;--muted:#8f8e86;
--ref:#3987e5;--cur:#d95926;--warn:#fab219;--crit:#e66767}}
:root[data-theme=dark]{color-scheme:dark;--bg:#111110;--surface:#1a1a19;--line:#2e2e2c;
--text:#f0efec;--text2:#c3c2b7;--muted:#8f8e86;--ref:#3987e5;--cur:#d95926;--warn:#fab219;--crit:#e66767}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}h2{font-size:17px;margin:32px 0 12px}
.sub{color:var(--text2);margin:0}
.hero{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between}
.status-pill{font-weight:600;padding:6px 14px;border-radius:999px;border:1px solid var(--line);
background:var(--surface)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:22px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.tile span{display:block;color:var(--text2);font-size:12px}.tile b{font-size:26px;font-weight:600}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 14px}
.toolbar button{font:inherit;border:1px solid var(--line);background:var(--surface);color:var(--text);
padding:5px 12px;border-radius:999px;cursor:pointer}
.toolbar button[aria-pressed=true]{background:var(--text);color:var(--surface);border-color:var(--text)}
.toolbar input{font:inherit;flex:1;min-width:160px;padding:6px 12px;border-radius:999px;
border:1px solid var(--line);background:var(--surface);color:var(--text)}
.legend{display:flex;gap:16px;color:var(--text2);font-size:13px;margin-left:auto}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.grid-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr));gap:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}
.card header{display:flex;justify-content:space-between;align-items:center;gap:8px}
.card h3{margin:0;font-size:15px;word-break:break-all}.card h3 small{color:var(--muted);font-weight:400;margin-left:6px}
.badge{font-size:12px;font-weight:600;padding:2px 10px;border-radius:999px;white-space:nowrap;border:1px solid}
.b-ok{color:var(--good);border-color:var(--good)}.b-warning{color:var(--warn);border-color:var(--warn)}
.b-drift{color:var(--crit);border-color:var(--crit)}
.kpis{display:flex;flex-wrap:wrap;gap:6px 22px;margin:10px 0 4px}.kpis span{display:block;font-size:11px;color:var(--text2)}
.kpis b{font-weight:600;font-variant-numeric:tabular-nums}
.notes{margin:6px 0;padding-left:18px;color:var(--text2);font-size:13px}
.body figure{margin:8px 0 0}.chart{width:100%;height:auto;display:block}
.chart .grid{stroke:var(--line);stroke-width:1}.chart .axis{stroke:var(--muted);stroke-width:1}
.chart .tick,.chart .lab{fill:var(--text2);font-size:11px;font-variant-numeric:tabular-nums}
.s-ref{fill:var(--ref)}.s-cur{fill:var(--cur)}.hit{fill:transparent}
.mark:hover .s-ref,.mark:hover .s-cur{opacity:.75}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--text2);font-weight:500;font-size:12px}
.mini{margin-top:10px;font-size:12px}.mini td{text-align:right}.mini thead th{text-align:right}
.overview{overflow-x:auto}.overview td.num{text-align:right}.overview a{color:var(--text);text-decoration:none}
.overview a:hover{text-decoration:underline}
.schema li{margin:3px 0}code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
footer{margin-top:40px;color:var(--muted);font-size:12px}
.hidden{display:none!important}
"""

JS = """
const btns=[...document.querySelectorAll('[data-filter]')],q=document.getElementById('q');
let f='all';
function apply(){const t=q.value.trim().toLowerCase();
document.querySelectorAll('.card,.overview tbody tr').forEach(el=>{
const ok=(f==='all'||el.dataset.status===f)&&(!t||el.dataset.name.includes(t));
el.classList.toggle('hidden',!ok)})}
btns.forEach(b=>b.addEventListener('click',()=>{f=b.dataset.filter;
btns.forEach(x=>x.setAttribute('aria-pressed',x===b));apply()}));
q.addEventListener('input',apply);
"""


def render_html(r: DriftReport) -> str:
    d = r.to_dict()
    s = d["summary"]
    status_txt = {"ok": "Sin drift relevante", "warning": "Cambios moderados", "drift": "Drift detectado"}[
        r.status
    ]
    status_color = {"ok": "var(--good)", "warning": "var(--warn)", "drift": "var(--crit)"}[r.status]

    overview_rows = "".join(
        f'<tr data-status="{c.status}" data-name="{escape(c.name.lower())}">'
        f'<td><span class="badge b-{c.status}">{ICON[c.status]} {LABEL[c.status]}</span></td>'
        f'<td><a href="#col-{escape(c.name)}"><code>{escape(c.name)}</code></a></td>'
        f"<td>{c.kind}</td><td class='num'>{_f(c.psi)}</td>"
        f"<td class='num'>{_f(c.p_value, 4)}</td>"
        f"<td class='num'>{_pct(c.null_rate_ref)} → {_pct(c.null_rate_cur)}</td></tr>"
        for c in r.columns
    )

    sc = r.schema
    schema_items = []
    if sc.removed:
        schema_items.append(f"<li>Columnas eliminadas: <code>{escape(', '.join(sc.removed))}</code></li>")
    if sc.added:
        schema_items.append(f"<li>Columnas nuevas: <code>{escape(', '.join(sc.added))}</code></li>")
    for k, (a, b) in sc.type_changed.items():
        schema_items.append(f"<li>Tipo cambiado en <code>{escape(k)}</code>: {a} → {b}</li>")
    schema_html = (
        (
            f'<h2>Cambios de esquema</h2><div class="panel"><ul class="schema">'
            f"{''.join(schema_items)}</ul></div>"
        )
        if schema_items
        else ""
    )

    cards = "".join(_card(c) for c in r.columns)
    payload = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reporte de drift · driftradar</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<div class="hero">
  <div>
    <h1>Reporte de drift</h1>
    <p class="sub"><b>{escape(r.reference_name)}</b> ({r.rows_ref:,} filas) →
      <b>{escape(r.current_name)}</b> ({r.rows_cur:,} filas) · generado {escape(r.generated_at)}</p>
  </div>
  <span class="status-pill" style="color:{status_color};border-color:{status_color}">
    {ICON[r.status]} {status_txt}</span>
</div>
<div class="tiles">
  <div class="tile"><span>Columnas analizadas</span><b>{s["columns_analyzed"]}</b></div>
  <div class="tile"><span>■ Drift (PSI ≥ {r.config.psi_drift})</span><b>{s["drift"]}</b></div>
  <div class="tile"><span>▲ Alerta</span><b>{s["warning"]}</b></div>
  <div class="tile"><span>● Estables</span><b>{s["ok"]}</b></div>
  <div class="tile"><span>% columnas con drift</span><b>{s["share_drifted"]:.0%}</b></div>
</div>
{schema_html}
<h2>Resumen por columna</h2>
<div class="toolbar">
  <button data-filter="all" aria-pressed="true">Todas</button>
  <button data-filter="drift" aria-pressed="false">■ Drift</button>
  <button data-filter="warning" aria-pressed="false">▲ Alerta</button>
  <button data-filter="ok" aria-pressed="false">● Estables</button>
  <input id="q" type="search" placeholder="Buscar columna…" aria-label="Buscar columna">
</div>
<div class="panel overview"><table>
<thead><tr><th>Estado</th><th>Columna</th><th>Tipo</th><th style="text-align:right">PSI</th>
<th style="text-align:right">p-valor</th><th style="text-align:right">Nulos ref → act</th></tr></thead>
<tbody>{overview_rows}</tbody></table></div>
<div class="toolbar"><h2 style="margin:24px 0 0">Distribuciones</h2>
  <div class="legend" style="margin-top:24px"><span><i style="background:var(--ref)"></i>Referencia</span>
  <span><i style="background:var(--cur)"></i>Actual</span></div></div>
<div class="grid-cards">{cards}</div>
<footer>driftradar v{escape(r.version)} · PSI: &lt;{r.config.psi_warning} estable,
{r.config.psi_warning}–{r.config.psi_drift} alerta, ≥{r.config.psi_drift} drift ·
p-valor de KS (numéricas) o χ² (categóricas), α={r.config.p_value}</footer>
</div>
<script type="application/json" id="driftradar-data">{payload}</script>
<script>{JS}</script>
</body></html>"""
