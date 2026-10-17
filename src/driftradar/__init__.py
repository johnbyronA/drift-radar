"""driftradar — detecta cambios (drift) entre dos versiones de un dataset."""

__version__ = "1.0.0"

from .config import Config
from .core import ColumnResult, DriftReport, SchemaChanges, compare
from .io import read_table

__all__ = [
    "ColumnResult",
    "Config",
    "DriftReport",
    "SchemaChanges",
    "__version__",
    "compare",
    "read_table",
]
