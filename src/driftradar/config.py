"""Configuración y umbrales. Se puede cargar desde un archivo TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass
class Config:
    """Umbrales y opciones del análisis.

    Los valores por defecto siguen convenciones usadas en riesgo de crédito y
    monitoreo de modelos (PSI 0.10 / 0.25).
    """

    psi_warning: float = 0.10
    psi_drift: float = 0.25
    p_value: float = 0.01
    """Nivel de significancia para KS / chi². Solo refuerza la severidad si el PSI ya avisa."""
    null_rate_warning: float = 0.05
    """Cambio absoluto en la tasa de nulos que dispara una alerta (5 puntos porcentuales)."""
    bins: int = 10
    max_categories: int = 30
    categorical_max_unique: int = 15
    """Columnas numéricas con <= este número de valores únicos se tratan como categóricas."""
    columns: list[str] | None = None
    """Si se define, solo se analizan estas columnas."""
    exclude: list[str] = field(default_factory=list)
    """Columnas a ignorar (IDs, timestamps de carga, etc.)."""

    def __post_init__(self) -> None:
        if not 0 < self.psi_warning < self.psi_drift:
            raise ValueError("Se requiere 0 < psi_warning < psi_drift")
        if not 0 < self.p_value < 1:
            raise ValueError("p_value debe estar entre 0 y 1")
        if self.bins < 2:
            raise ValueError("bins debe ser >= 2")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Claves de configuración desconocidas: {sorted(unknown)}")
        return cls(**data)

    @classmethod
    def from_toml(cls, path: str | Path) -> Config:
        """Lee ``driftradar.toml`` o la sección ``[tool.driftradar]`` de ``pyproject.toml``."""
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        if "tool" in data and "driftradar" in data["tool"]:
            data = data["tool"]["driftradar"]
        return cls.from_dict(data)
