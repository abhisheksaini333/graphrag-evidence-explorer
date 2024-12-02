FROM node:20.10.0-bookworm-slim@sha256:5c714c3e90f66a2cbfa266b90a4d7adcd63453cd730aa2d13cba84b260bea2e6 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY web/ ./
RUN npm test && npm run build

FROM python:3.10.11-slim-bullseye@sha256:fd86924ba14682eb11a3c244f60a35b5dfe3267cbf26d883fb5c14813ce926f1
ARG TARGETARCH
RUN test "$TARGETARCH" = amd64
WORKDIR /app
COPY bootstrap-linux-x86_64.lock graph-linux-x86_64.lock ./
COPY scripts/bootstrap_lancedb.py scripts/bootstrap_lancedb.py
COPY dependencies/lancedb-originals.json dependencies/lancedb-originals.json
RUN pip install --no-cache-dir --no-deps --require-hashes -r bootstrap-linux-x86_64.lock && python scripts/bootstrap_lancedb.py --platform linux-x86_64 --output /tmp/original-wheels && pip install --no-cache-dir --no-deps --require-hashes --find-links /tmp/original-wheels -r graph-linux-x86_64.lock && pip check && rm -rf /tmp/original-wheels
COPY explorer/ explorer/
COPY tests/ tests/
COPY scripts/ scripts/
COPY examples/ examples/
COPY dependencies/ dependencies/
COPY --from=web /web/dist/ web/dist/
RUN mkdir -p /data && chown 65532:65532 /data
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 NUMBA_CACHE_DIR=/tmp/numba
USER 65532:65532
EXPOSE 8089
HEALTHCHECK --interval=15s --timeout=3s --start-period=300s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8089/api/health',timeout=2)"
CMD ["python","-m","explorer.api","--host","0.0.0.0","--database","/data/corpus.sqlite","--model-url","http://graph-model:8090"]
