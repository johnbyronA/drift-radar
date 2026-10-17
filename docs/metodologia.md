# Metodología

driftradar responde una pregunta concreta: **¿los datos de hoy se parecen a los datos con los que
construí mi análisis, tablero o modelo?** Para cada columna común a los dos datasets calcula una
medida de *magnitud* del cambio (PSI), una prueba de *significancia* (KS o χ²) y varias
verificaciones de calidad.

## 1. Tipo de columna

| Condición | Tipo | Métricas |
|---|---|---|
| `datetime64` | datetime | PSI, KS, Wasserstein/σ sobre el timestamp |
| numérica con > 15 valores únicos | numeric | PSI, KS, Wasserstein/σ |
| numérica con ≤ 15 valores únicos, booleana o texto | categorical | PSI, χ² |

El umbral de 15 se configura con `categorical_max_unique`.

## 2. Population Stability Index (PSI)

$$PSI = \sum_i (A_i - E_i)\,\ln\frac{A_i}{E_i}$$

donde $E_i$ es la proporción de la referencia y $A_i$ la del dataset actual en el bin $i$.

- **Numéricas:** bins por cuantiles de la referencia (10 por defecto), más dos bins abiertos que
  capturan valores por debajo del mínimo o por encima del máximo de referencia. Así un valor nunca
  visto sí suma al PSI.
- **Categóricas:** una categoría = un bin. Las categorías menos frecuentes (más allá de
  `max_categories`) se agrupan en `__otros__` para que el índice no explote con alta cardinalidad.
- Se aplica suavizado ($\varepsilon = 10^{-4}$) para evitar $\ln 0$ en bins vacíos.

| PSI | Estado | Lectura |
|---|---|---|
| < 0.10 | 🟢 Estable | Sin cambio relevante |
| 0.10 – 0.25 | 🟡 Alerta | Cambio moderado: revisar |
| ≥ 0.25 | 🔴 Drift | Cambio significativo: la población ya no es la misma |

Estos cortes son la convención de la industria de riesgo de crédito y se pueden cambiar.

## 3. ¿Por qué el estado se basa en PSI y no en el p-valor?

Con miles de filas, KS y χ² marcan como "significativa" casi cualquier diferencia, aunque sea
irrelevante en la práctica. Por eso:

- El **estado** se decide por la magnitud (PSI).
- El **p-valor** se reporta como evidencia. Si es significativo pero el PSI es pequeño, se agrega
  la nota *"diferencia estadísticamente significativa pero de magnitud pequeña"*.

## 4. Verificaciones adicionales

| Verificación | Efecto |
|---|---|
| Cambio absoluto en % de nulos ≥ `null_rate_warning` (5 pp) | sube a 🟡 Alerta como mínimo |
| Categorías nuevas o desaparecidas | nota con ejemplos y % de filas afectadas |
| > 1 % de valores actuales fuera del rango [min, max] de referencia | nota |
| Columna eliminada | estado global 🔴 Drift |
| Columna nueva o cambio de tipo | estado global 🟡 Alerta como mínimo |

## 5. Wasserstein normalizado

Distancia de Wasserstein (earth mover's distance) dividida por la desviación estándar de la
referencia. Se lee como "cuántas desviaciones estándar se movió la distribución". Es informativa,
no afecta el estado.

## 6. Limitaciones

- Analiza cada columna por separado (drift univariado). No detecta cambios en la relación entre
  columnas si las marginales se mantienen.
- PSI depende del binning; con muy pocas filas (< 200) los resultados son ruidosos.
- Para columnas de fecha casi siempre habrá drift si los periodos son distintos: exclúyelas con
  `--exclude` salvo que quieras validar la ventana temporal.
