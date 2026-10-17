# Contribuir

1. Haz fork y crea una rama: `git checkout -b feat/mi-cambio`
2. Instala: `make install` (o `pip install -e ".[dev]"`) y opcionalmente `pre-commit install`
3. Asegúrate de que pasen `make lint` y `make test` (cobertura mínima 85 %)
4. Abre un Pull Request describiendo el cambio y cómo probarlo

Para reportar un bug, abre un issue con: versión (`driftradar --version`), comando ejecutado,
salida obtenida y, si es posible, un dataset mínimo (sintético) que lo reproduzca.
