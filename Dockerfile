# syntax=docker/dockerfile:1.7
# DRAFT / UNVERIFIED: this file has never been built (Docker Desktop's engine was not running when checked).
# python/requirements-lpbf-linux-py312.lock now exists (uv, manylinux_2_28, CPython 3.12.15) and was install-checked with --require-hashes
# in WSL Ubuntu 22.04 (LPBF engineering 40 OK + 1 skip, build-job PASS, CMU 8 OK, Phase 6a golden tests OK, fingerprint unchanged).
# See docs/APPLICATION_PACKAGING_NOTES.md.

FROM node:24-bookworm-slim AS node-src

# Base: CPython 3.12 with the Node 24 runtime copied in.
FROM python:3.12-slim-bookworm AS base
COPY --from=node-src /usr/local/bin/node /usr/local/bin/node
COPY --from=node-src /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Node dependencies (all, for build and test).
FROM base AS node-deps
COPY package.json package-lock.json ./
RUN npm ci

# Python environment from the hash-locked Linux CPU lock (to be generated).
FROM base AS py-deps
COPY python/requirements-lpbf-linux-py312.lock /tmp/requirements.lock
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

# Verification target: docker build --target verify .
# The unit test list is the tests/*.test.ts(x) glob minus scripts/ci-unit-tests.txt,
# the same rule as .github/workflows/ci.yml.
FROM base AS verify
ENV METALLIX_PYTHON=/opt/venv/bin/python AIRGAPPED=1 CI=1
COPY --from=py-deps /opt/venv /opt/venv
COPY --from=node-deps /app/node_modules ./node_modules
COPY . .
RUN <<'EOF' bash -e
npm run lint
excluded="$(grep -v '^#' scripts/ci-unit-tests.txt | grep -v '^$' || true)"
files="$(ls tests/*.test.ts tests/*.test.tsx | { grep -vxF "$excluded" || true; })"
node_modules/.bin/tsx --test $files
npm run build
/opt/venv/bin/python python/test_eagar_tsai.py
/opt/venv/bin/python python/test_goldak_fabbro.py
/opt/venv/bin/python python/test_lpbf_meltpool_accuracy.py
EOF

# Production dependencies only.
FROM base AS prod-deps
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Runtime image (default target). Runs as a non-root user.
# Every path the server or the Python worker writes is either redirected to /data via
# environment variables or is a WORKDIR-relative default that is created and chowned
# below, so the defaults also work when the variables are unset.
FROM base AS runtime
ENV NODE_ENV=production \
    PORT=3000 \
    AIRGAPPED=1 \
    METALLIX_PYTHON=/opt/venv/bin/python \
    METALLIKSA_LPBF_SOURCE_ROOT=/data/lpbf-sources \
    METALLIKSA_LPBF_RUN_ROOT=/data/lpbf-runs \
    METALLIKSA_LPBF_BUNDLE_ROOT=/data/lpbf-run-bundles \
    METALLIKSA_JOB_ROOT=/data/lpbf-jobs \
    RESEARCH_REGISTRY_DIR=/data/research-registry
RUN useradd --system --uid 10001 --home-dir /app metalliksa \
 && mkdir -p /data \
      /app/.lpbf-sources /app/.lpbf-runs /app/.lpbf-run-bundles /app/.lpbf-jobs \
      /app/.research-registry /app/.runtime /app/.lpbf-surrogates \
 && chown -R metalliksa /data /app
COPY --from=py-deps /opt/venv /opt/venv
COPY --from=prod-deps --chown=metalliksa /app/node_modules ./node_modules
# dist comes from the verify stage so an image is only produced from a verified build.
COPY --from=verify --chown=metalliksa /app/dist ./dist
COPY --chown=metalliksa package.json ./
# python/ is owned by the app user: python/tmp* scratch directories and relative writes
# made with the worker's cwd are created there at run time.
COPY --chown=metalliksa python ./python
COPY --chown=metalliksa data ./data
COPY --chown=metalliksa assets ./assets
# docs/sources/in625 is read at run time (server/lpbfPropertySourceCatalog.ts resolves it
# against the working directory; lpbfSourceArchiveService archives from it).
COPY --chown=metalliksa docs/sources/in625 ./docs/sources/in625
# Tracked surrogate models. Only python/phase9_surrogate.py (offline scripts/tests, not called by
# the server) uses .lpbf-surrogates; it imports sklearn/joblib, which the lpbf lock does not
# provide, so this copy is inert unless scikit-learn is added to the image.
COPY --chown=metalliksa .lpbf-surrogates ./.lpbf-surrogates
USER metalliksa
VOLUME ["/data"]
EXPOSE 3000
CMD ["node", "dist/server.cjs"]
