"""Motor principal: compara dos DataFrames y construye un ``DriftReport``."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
import pandas as pd

from . import __version__, metrics
from .config import Config

Status = Literal["ok", "warning", "drift"]
Kind = Literal["numeric", "categorical", "datetime"]
_RANK = {"ok": 0, "warning": 1, "drift": 2}


def worst(*statuses: Status) -> Status:
    return max(statuses, key=lambda s: _RANK[s]) if statuses else "ok"


@dataclass
class ColumnResult:
    name: str
    kind: Kind
    status: Status
    psi: float
    test: str
    statistic: float
    p_value: float
    null_rate_ref: float
    null_rate_cur: float
    wasserstein: float | None = None
    summary_ref: dict[str, Any] = field(default_factory=dict)
    summary_cur: dict[str, Any] = field(default_factory=dict)
    histogram: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class SchemaChanges:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    type_changed: dict[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def status(self) -> Status:
        if self.removed:
            return "drift"
        if self.added or self.type_changed:
            return "warning"
        return "ok"


@dataclass
class DriftReport:
    rows_ref: int
    rows_cur: int
    columns: list[ColumnResult]
    schema: SchemaChanges
    config: Config
    reference_name: str = "referencia"
    current_name: str = "actual"
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))
    version: str = __version__

    # ---- resumen -------------------------------------------------------
    @property
    def status(self) -> Status:
        return worst(self.schema.status, *(c.status for c in self.columns))

    def by_status(self, status: Status) -> list[ColumnResult]:
        return [c for c in self.columns if c.status == status]

    @property
    def drifted_columns(self) -> list[str]:
        return [c.name for c in self.by_status("drift")]

    @property
    def share_drifted(self) -> float:
        return len(self.drifted_columns) / len(self.columns) if self.columns else 0.0

    # ---- exportación ---------------------------------------------------
    def to_dict(self, include_histograms: bool = False) -> dict[str, Any]:
        cols = []
        for c in self.columns:
            d = asdict(c)
            if not include_histograms:
                d.pop("histogram")
            cols.append(d)
        return _clean(
            {
                "driftradar_version": self.version,
                "generated_at": self.generated_at,
                "reference": {"name": self.reference_name, "rows": self.rows_ref},
                "current": {"name": self.current_name, "rows": self.rows_cur},
                "status": self.status,
                "summary": {
                    "columns_analyzed": len(self.columns),
                    "drift": len(self.by_status("drift")),
                    "warning": len(self.by_status("warning")),
                    "ok": len(self.by_status("ok")),
                    "share_drifted": round(self.share_drifted, 4),
                },
                "schema": {
                    "added": self.schema.added,
                    "removed": self.schema.removed,
                    "type_changed": {k: list(v) for k, v in self.schema.type_changed.items()},
                },
                "thresholds": asdict(self.config),
                "columns": cols,
            }
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        from .report.markdown import render_markdown

        return render_markdown(self)

    def to_html(self) -> str:
        from .report.html import render_html

        return render_html(self)

    def to_frame(self) -> pd.DataFrame:
        """Resultados por columna como DataFrame (útil en notebooks)."""
        rows = [
            {
                "columna": c.name,
                "tipo": c.kind,
                "estado": c.status,
                "psi": c.psi,
                "prueba": c.test,
                "p_valor": c.p_value,
                "nulos_ref": c.null_rate_ref,
                "nulos_act": c.null_rate_cur,
            }
            for c in self.columns
        ]
        return pd.DataFrame(rows).sort_values("psi", ascending=False, ignore_index=True)


def _clean(obj: Any) -> Any:
    """Convierte NaN/inf y tipos numpy en valores serializables a JSON."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return None if math.isnan(f) or math.isinf(f) else round(f, 6)
    return obj


# ---------------------------------------------------------------------------
def _kind(s: pd.Series, cfg: Config) -> Kind:
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_bool_dtype(s):
        return "categorical"
    if pd.api.types.is_numeric_dtype(s):
        return "categorical" if s.nunique(dropna=True) <= cfg.categorical_max_unique else "numeric"
    return "categorical"


def _dt_to_ns(s: pd.Series) -> np.ndarray:
    """Fechas a nanosegundos desde epoch, independiente de la resolución (pandas 2/3)."""
    s = s.dt.tz_localize(None) if getattr(s.dt, "tz", None) is not None else s
    return s.astype("datetime64[ns]").astype("int64").to_numpy(dtype=float)


def _human(v: float) -> str:
    a = abs(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if a >= div:
            return f"{v / div:,.3g}{suf}"
    return f"{v:,.4g}"


def _num_summary(x: np.ndarray, is_dt: bool) -> dict[str, Any]:
    if len(x) == 0:
        return {}
    q = np.quantile(x, [0, 0.5, 1])
    if is_dt:
        fmt = lambda v: str(pd.Timestamp(int(v)).date())  # noqa: E731
        return {"min": fmt(q[0]), "mediana": fmt(q[1]), "max": fmt(q[2])}
    return {
        "media": float(np.mean(x)),
        "desv": float(np.std(x)),
        "min": float(q[0]),
        "mediana": float(q[1]),
        "max": float(q[2]),
    }


def _cat_summary(s: pd.Series) -> dict[str, Any]:
    if s.empty:
        return {}
    vc = s.astype(str).value_counts(normalize=True)
    return {"unicos": int(vc.size), "top": str(vc.index[0]), "top_pct": float(vc.iloc[0])}


def _num_histogram(ref: np.ndarray, cur: np.ndarray, is_dt: bool, bins: int = 20) -> dict:
    both = np.concatenate([ref, cur])
    if both.size == 0:
        return {}
    lo, hi = np.quantile(both, [0.005, 0.995])
    if lo == hi:
        lo, hi = both.min(), both.max() + 1
    edges = np.linspace(lo, hi, bins + 1)
    r, _ = np.histogram(np.clip(ref, lo, hi), edges)
    c, _ = np.histogram(np.clip(cur, lo, hi), edges)
    labels = [str(pd.Timestamp(int(e)).date()) for e in edges] if is_dt else [_human(e) for e in edges]
    return {
        "type": "numeric",
        "edges": labels,
        "ref": (r / max(r.sum(), 1)).tolist(),
        "cur": (c / max(c.sum(), 1)).tolist(),
    }


def _analyze_column(name: str, r: pd.Series, c: pd.Series, cfg: Config) -> ColumnResult:
    kind = _kind(r, cfg)
    nr_ref = float(r.isna().mean()) if len(r) else 0.0
    nr_cur = float(c.isna().mean()) if len(c) else 0.0
    r_nn, c_nn = r.dropna(), c.dropna()
    notes: list[str] = []
    wass: float | None = None

    if kind in ("numeric", "datetime"):
        is_dt = kind == "datetime"
        if is_dt:
            rx = _dt_to_ns(r_nn)
            cx = _dt_to_ns(pd.to_datetime(c_nn, errors="coerce").dropna())
        else:
            rx = r_nn.to_numpy(dtype=float)
            cx = pd.to_numeric(c_nn, errors="coerce").dropna().to_numpy(dtype=float)
        psi = metrics.psi_numeric(rx, cx, cfg.bins)
        stat, p = metrics.ks_test(rx, cx)
        test = "ks"
        wass = metrics.wasserstein_normalized(rx, cx)
        s_ref, s_cur = _num_summary(rx, is_dt), _num_summary(cx, is_dt)
        hist = _num_histogram(rx, cx, is_dt)
        if not is_dt and len(rx) and len(cx):
            lo, hi = rx.min(), rx.max()
            out = float(((cx < lo) | (cx > hi)).mean())
            if out > 0.01:
                notes.append(f"{out:.1%} de los valores actuales caen fuera del rango de referencia")
    else:
        psi = metrics.psi_categorical(r_nn, c_nn, cfg.max_categories)
        stat, p = metrics.chi2_test(r_nn, c_nn, cfg.max_categories)
        test = "chi2"
        s_ref, s_cur = _cat_summary(r_nn), _cat_summary(c_nn)
        cats, rf, cf = metrics.category_frequencies(r_nn, c_nn, cfg.max_categories)
        order = np.argsort(-(rf + cf))[:12]
        hist = {
            "type": "categorical",
            "labels": [cats[i] for i in order],
            "ref": [float(rf[i]) for i in order],
            "cur": [float(cf[i]) for i in order],
        }
        new = set(c_nn.astype(str).unique()) - set(r_nn.astype(str).unique())
        if new:
            share = float(c_nn.astype(str).isin(new).mean())
            sample = ", ".join(sorted(new)[:3])
            notes.append(f"{len(new)} categoría(s) nueva(s) ({share:.1%} de filas): {sample}")
        gone = set(r_nn.astype(str).unique()) - set(c_nn.astype(str).unique())
        if gone and len(c_nn):
            notes.append(f"{len(gone)} categoría(s) de referencia ya no aparecen")

    # --- severidad ---
    if math.isnan(psi):
        status: Status = "warning"
        notes.append("Sin datos suficientes para calcular PSI")
    elif psi >= cfg.psi_drift:
        status = "drift"
    elif psi >= cfg.psi_warning:
        status = "warning"
    else:
        status = "ok"
        if not math.isnan(p) and p < cfg.p_value:
            notes.append("Diferencia estadísticamente significativa pero de magnitud pequeña")

    delta_null = nr_cur - nr_ref
    if abs(delta_null) >= cfg.null_rate_warning:
        status = worst(status, "warning")
        notes.append(f"Tasa de nulos cambió {delta_null:+.1%} ({nr_ref:.1%} → {nr_cur:.1%})")

    return ColumnResult(
        name=name,
        kind=kind,
        status=status,
        psi=psi,
        test=test,
        statistic=stat,
        p_value=p,
        null_rate_ref=nr_ref,
        null_rate_cur=nr_cur,
        wasserstein=wass,
        summary_ref=s_ref,
        summary_cur=s_cur,
        histogram=hist,
        notes=notes,
    )


def compare(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    config: Config | None = None,
    *,
    reference_name: str = "referencia",
    current_name: str = "actual",
) -> DriftReport:
    """Compara ``current`` contra ``reference`` y devuelve un :class:`DriftReport`.

    >>> import pandas as pd, driftradar
    >>> ref = pd.DataFrame({"x": range(100)})
    >>> driftradar.compare(ref, ref).status
    'ok'
    """
    cfg = config or Config()
    if not isinstance(reference, pd.DataFrame) or not isinstance(current, pd.DataFrame):
        raise TypeError("reference y current deben ser pandas.DataFrame")
    if reference.empty:
        raise ValueError("El dataset de referencia está vacío")

    ref_cols, cur_cols = list(reference.columns), list(current.columns)
    schema = SchemaChanges(
        added=[c for c in cur_cols if c not in ref_cols],
        removed=[c for c in ref_cols if c not in cur_cols],
    )
    common = [c for c in ref_cols if c in cur_cols and c not in cfg.exclude]
    if cfg.columns is not None:
        missing = set(cfg.columns) - set(common)
        if missing:
            raise ValueError(f"Columnas solicitadas no existen en ambos datasets: {sorted(missing)}")
        common = [c for c in common if c in cfg.columns]

    results = []
    for col in common:
        r, c = reference[col], current[col]
        if _kind(r, cfg) != _kind(c, cfg) and str(r.dtype) != str(c.dtype):
            schema.type_changed[col] = (str(r.dtype), str(c.dtype))
        results.append(_analyze_column(col, r, c, cfg))

    results.sort(key=lambda x: (-_RANK[x.status], -(x.psi if not math.isnan(x.psi) else 0)))
    return DriftReport(
        rows_ref=len(reference),
        rows_cur=len(current),
        columns=results,
        schema=schema,
        config=cfg,
        reference_name=reference_name,
        current_name=current_name,
    )
