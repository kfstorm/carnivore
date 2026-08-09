# syntax=docker/dockerfile:1

ARG BASE_IMAGE_REF=python:3.13.0-slim@sha256:0de818129b26ed8f46fd772f540c80e277b67a28229531a1ba0fdacfaed19bcb

FROM ${BASE_IMAGE_REF}

ARG BASE_IMAGE_REF
ARG TARGETARCH

ENV HOME=/home/carnivore \
    NODE_ENV=production \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY docker/core.lock /opt/carnivore/core.lock
COPY docker/requirements-core.txt /opt/carnivore/requirements-core.txt
COPY carnivore-lib/carnivore/readability/package.json carnivore-lib/carnivore/readability/package-lock.json /app/carnivore/readability/

RUN set -eux; \
    declared_base="${BASE_IMAGE_REF}"; \
    . /opt/carnivore/core.lock; \
    test "${declared_base}" = "${BASE_IMAGE_REF}"; \
    case "${TARGETARCH}" in \
        amd64) \
            node_arch=x64; \
            node_sha256="${NODE_SHA256_AMD64}"; \
            chromium_file=chromium-linux.zip; \
            chromium_sha256="${CHROMIUM_SHA256_AMD64}"; \
            pandoc_arch=amd64; \
            pandoc_sha256="${PANDOC_SHA256_AMD64}"; \
            monolith_arch=x86_64; \
            monolith_sha256="${MONOLITH_SHA256_AMD64}"; \
            libssl_arch=; \
            libssl_sha256=; \
            ;; \
        arm64) \
            node_arch=arm64; \
            node_sha256="${NODE_SHA256_ARM64}"; \
            chromium_file=chromium-linux-arm64.zip; \
            chromium_sha256="${CHROMIUM_SHA256_ARM64}"; \
            pandoc_arch=arm64; \
            pandoc_sha256="${PANDOC_SHA256_ARM64}"; \
            monolith_arch=aarch64; \
            monolith_sha256="${MONOLITH_SHA256_ARM64}"; \
            libssl_arch=arm64; \
            libssl_sha256="${LIBSSL1_1_SHA256_ARM64}"; \
            ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libatomic1 \
        unzip \
        xz-utils; \
    node_url="${NODE_DOWNLOAD_BASE}/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 "${node_url}" -o /tmp/node.tar.xz; \
    printf '%s  %s\n' "${node_sha256}" /tmp/node.tar.xz | sha256sum -c -; \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 --no-same-owner; \
    pandoc_url="${PANDOC_DOWNLOAD_BASE}/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-${pandoc_arch}.tar.gz"; \
    curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 "${pandoc_url}" -o /tmp/pandoc.tar.gz; \
    printf '%s  %s\n' "${pandoc_sha256}" /tmp/pandoc.tar.gz | sha256sum -c -; \
    tar -xzf /tmp/pandoc.tar.gz -C /usr/local --strip-components=1; \
    monolith_url="${MONOLITH_DOWNLOAD_BASE}/v${MONOLITH_VERSION}/monolith-gnu-linux-${monolith_arch}"; \
    curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 "${monolith_url}" -o /usr/local/bin/monolith; \
    printf '%s  %s\n' "${monolith_sha256}" /usr/local/bin/monolith | sha256sum -c -; \
    chmod 0755 /usr/local/bin/monolith; \
    if [ -n "${libssl_sha256}" ]; then \
        libssl_url="${LIBSSL1_1_DOWNLOAD_BASE}/libssl1.1_${LIBSSL1_1_VERSION}_${libssl_arch}.deb"; \
        curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 "${libssl_url}" -o /tmp/libssl1.1.deb; \
        printf '%s  %s\n' "${libssl_sha256}" /tmp/libssl1.1.deb | sha256sum -c -; \
        dpkg --unpack /tmp/libssl1.1.deb; \
    fi; \
    python -m pip install --no-cache-dir -r /opt/carnivore/requirements-core.txt; \
    playwright install-deps chromium; \
    chromium_url="${PLAYWRIGHT_DOWNLOAD_BASE}/builds/chromium/${CHROMIUM_REVISION}/${chromium_file}"; \
    mkdir -p "${PLAYWRIGHT_BROWSERS_PATH}/chromium-${CHROMIUM_REVISION}"; \
    curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 "${chromium_url}" -o /tmp/chromium.zip; \
    printf '%s  %s\n' "${chromium_sha256}" /tmp/chromium.zip | sha256sum -c -; \
    unzip -q /tmp/chromium.zip -d "${PLAYWRIGHT_BROWSERS_PATH}/chromium-${CHROMIUM_REVISION}"; \
    touch "${PLAYWRIGHT_BROWSERS_PATH}/chromium-${CHROMIUM_REVISION}/INSTALLATION_COMPLETE"; \
    cd /app/carnivore/readability; \
    test "$(sha256sum package-lock.json | cut -d' ' -f1)" = "${NPM_LOCK_SHA256}"; \
    npm ci --omit=dev --no-audit --no-fund; \
    rm -rf /root/.cache /root/.npm /tmp/*; \
    rm -rf /usr/local/include/node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack; \
    rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack; \
    apt-get purge -y --auto-remove curl unzip xz-utils; \
    rm -rf /var/lib/apt/lists/*

COPY carnivore-lib/carnivore/__init__.py \
    carnivore-lib/carnivore/__main__.py \
    carnivore-lib/carnivore/cache.py \
    carnivore-lib/carnivore/cli.py \
    carnivore-lib/carnivore/convert.py \
    carnivore-lib/carnivore/extract.py \
    carnivore-lib/carnivore/models.py \
    carnivore-lib/carnivore/pipeline.py \
    carnivore-lib/carnivore/process.py \
    carnivore-lib/carnivore/render.py \
    /app/carnivore/
COPY carnivore-lib/carnivore/readability/index.mjs /app/carnivore/readability/index.mjs
COPY entrypoint.sh /app/entrypoint.sh

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin carnivore \
    && mkdir -p /cache \
    && chown -R carnivore:carnivore /app /cache /ms-playwright /home/carnivore

USER carnivore

ENTRYPOINT ["/app/entrypoint.sh"]
