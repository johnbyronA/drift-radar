"""Uso de driftradar desde Python. Ejecutar con: ``python examples/quickstart.py``."""

from pathlib import Path

import driftradar
from driftradar import Config

HERE = Path(__file__).parent
ref = driftradar.read_table(HERE / "data" / "solicitudes_agosto.csv", parse_dates=["fecha"])
cur = driftradar.read_table(HERE / "data" / "solicitudes_septiembre.csv", parse_dates=["fecha"])

report = driftradar.compare(ref, cur, Config(exclude=["id_solicitud", "fecha"]))

print("Estado global:", report.status)
print("Columnas con drift:", report.drifted_columns)
print(report.to_frame().head(10).to_string(index=False))

out = HERE / "reporte.html"
out.write_text(report.to_html(), encoding="utf-8")
print(f"Reporte HTML → {out}")
