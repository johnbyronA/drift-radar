# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels ".[parquet]"

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/johnbyronA/drift-radar" \
      org.opencontainers.image.description="driftradar: detección de drift en datasets" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --create-home --uid 10001 app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
USER app
WORKDIR /data
ENTRYPOINT ["driftradar"]
CMD ["--help"]
