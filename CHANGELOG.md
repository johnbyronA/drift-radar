# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [SemVer](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-17
### Añadido
- Motor `compare()` con PSI, Kolmogorov–Smirnov, χ² y Wasserstein normalizado.
- Detección de cambios de esquema (columnas nuevas, eliminadas y cambios de tipo).
- Alertas por cambio en tasa de nulos, categorías nuevas y valores fuera de rango.
- Reportes HTML autocontenido (modo claro/oscuro, filtros), JSON y Markdown.
- CLI `driftradar compare` / `driftradar demo` con códigos de salida para CI.
- GitHub Action compuesta, imagen Docker y configuración TOML.
