"""Métricas estadísticas de drift.

Todas las funciones son puras (sin efectos secundarios) y reciben arrays/Series
ya limpios de nulos. El manejo de nulos se hace en ``core``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

EPS = 1e-4
OTHER = "__otros__"


def _psi_from_props(ref_p: np.ndarray, cur_p: np.ndarray) -> float:
    ref_p = np.clip(ref_p, EPS, None)
    cur_p = np.clip(cur_p, EPS, None)
    ref_p = ref_p / ref_p.sum()
    cur_p = cur_p / cur_p.sum()
    return float(np.sum((cur_p - ref_p) * np.log(cur_p / ref_p)))


def quantile_edges(ref: np.ndarray, bins: int = 10) -> np.ndarray:
    """Bordes de bins por cuantiles de la referencia, abiertos en los extremos."""
    qs = np.quantile(ref, np.linspace(0, 1, bins + 1))
    # Incluye min y max (ligeramente desplazado) para aislar valores fuera del rango de referencia.
    qs[-1] = np.nextafter(qs[-1], np.inf)
    inner = np.unique(qs)
    return np.concatenate(([-np.inf], inner, [np.inf]))


def psi_numeric(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index para variables numéricas.

    Usa bins por cuantiles de la referencia, de modo que cada bin tiene ~1/bins
    de la masa de referencia. Valores de referencia típicos:
    < 0.10 estable · 0.10–0.25 cambio moderado · >= 0.25 cambio significativo.
    """
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    edges = quantile_edges(ref, bins)
    ref_c, _ = np.histogram(ref, edges)
    cur_c, _ = np.histogram(cur, edges)
    return _psi_from_props(ref_c / ref_c.sum(), cur_c / cur_c.sum())


def category_frequencies(
    ref: pd.Series, cur: pd.Series, max_categories: int = 30
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Frecuencias relativas alineadas. Agrupa la cola larga en ``__otros__``."""
    ref = ref.astype(str)
    cur = cur.astype(str)
    top = ref.value_counts().index[:max_categories].tolist()
    for c in cur.value_counts().index:
        if len(top) >= max_categories * 2:
            break
        if c not in top:
            top.append(c)
    keep = set(top)
    ref_m = ref.where(ref.isin(keep), OTHER)
    cur_m = cur.where(cur.isin(keep), OTHER)
    cats = top + ([OTHER] if (ref_m == OTHER).any() or (cur_m == OTHER).any() else [])
    ref_f = ref_m.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    cur_f = cur_m.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    return cats, ref_f, cur_f


def psi_categorical(ref: pd.Series, cur: pd.Series, max_categories: int = 30) -> float:
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    _, rf, cf = category_frequencies(ref, cur, max_categories)
    return _psi_from_props(rf, cf)


def ks_test(ref: np.ndarray, cur: np.ndarray) -> tuple[float, float]:
    """Kolmogorov–Smirnov de dos muestras. Devuelve (estadístico, p-valor)."""
    if len(ref) < 2 or len(cur) < 2:
        return float("nan"), float("nan")
    res = stats.ks_2samp(ref, cur)
    return float(res.statistic), float(res.pvalue)


def chi2_test(ref: pd.Series, cur: pd.Series, max_categories: int = 30) -> tuple[float, float]:
    """Chi-cuadrado de homogeneidad sobre la tabla de contingencia ref vs cur."""
    if len(ref) == 0 or len(cur) == 0:
        return float("nan"), float("nan")
    _, rf, cf = category_frequencies(ref, cur, max_categories)
    table = np.vstack([rf * len(ref), cf * len(cur)])
    table = table[:, table.sum(axis=0) > 0]
    if table.shape[1] < 2:
        return 0.0, 1.0
    chi2, p, _, _ = stats.chi2_contingency(table)
    return float(chi2), float(p)


def wasserstein_normalized(ref: np.ndarray, cur: np.ndarray) -> float:
    """Distancia de Wasserstein dividida por la desviación estándar de la referencia."""
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    scale = float(np.std(ref)) or 1.0
    return float(stats.wasserstein_distance(ref, cur) / scale)
