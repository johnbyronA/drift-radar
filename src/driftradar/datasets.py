"""Datasets sintéticos para demos y pruebas (sin datos reales ni personales).

Simula solicitudes de crédito de una fintech: un mes de referencia y un mes
"actual" donde cambia la mezcla de canales, sube el ingreso declarado, aparece
un canal nuevo y se degrada la calidad de un campo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

CITIES = ["Medellín", "Bogotá", "Cali", "Barranquilla", "Bucaramanga", "Pereira"]


def make_demo(n: int = 5000, seed: int = 42, drift: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve ``(referencia, actual)``. Con ``drift=False`` ambos vienen de la misma distribución."""
    rng = np.random.default_rng(seed)

    def batch(start: str, shifted: bool) -> pd.DataFrame:
        k = 1 if shifted else 0
        channels = ["app", "web", "aliado", "oficina"] + (["whatsapp"] if shifted else [])
        p_ch = [0.30, 0.25, 0.25, 0.20] if not shifted else [0.42, 0.18, 0.15, 0.10, 0.15]
        df = pd.DataFrame(
            {
                "id_solicitud": np.arange(n) + (n if shifted else 0),
                "fecha": pd.Timestamp(start) + pd.to_timedelta(rng.integers(0, 30, n), unit="D"),
                "edad": np.clip(rng.normal(36 - 2 * k, 10, n), 18, 80).round(),
                "ingreso_mensual": rng.lognormal(np.log(3_200_000) + 0.25 * k, 0.55, n).round(-3),
                "monto_solicitado": rng.lognormal(np.log(6_000_000), 0.7, n).round(-4),
                "plazo_meses": rng.choice([12, 24, 36, 48], n, p=[0.2, 0.35, 0.3, 0.15]),
                "ciudad": rng.choice(CITIES, n, p=[0.3, 0.3, 0.15, 0.1, 0.08, 0.07]),
                "canal": rng.choice(channels, n, p=p_ch),
                "score_buro": np.clip(rng.normal(680 - 25 * k, 70, n), 300, 950).round(),
                "tiene_vivienda": rng.random(n) < 0.42,
            }
        )
        email_null = 0.03 + 0.12 * k
        df["email_dominio"] = rng.choice(
            ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com"], n, p=[0.55, 0.25, 0.12, 0.08]
        )
        df.loc[rng.random(n) < email_null, "email_dominio"] = None
        return df

    ref = batch("2026-08-01", shifted=False)
    cur = batch("2026-09-01", shifted=drift)
    if not drift:
        cur["fecha"] = ref["fecha"].sample(frac=1, random_state=seed).to_numpy()
    return ref, cur
