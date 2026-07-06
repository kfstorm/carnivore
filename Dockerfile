FROM python:3.13.0-slim

ENV NODE_ENV=production

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    jq \
    curl \
    git \
    unzip \
    && rm -rf /var/lib/apt/lists/*
ARG PANDOC_VERSION=3.10
RUN curl -fsSL "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-$(dpkg --print-architecture).tar.gz" -o pandoc.tar.gz && \
    tar -xzf pandoc.tar.gz -C /usr/local --strip-components 1 && \
    rm pandoc.tar.gz
ARG TARGETARCH
ARG MONOLITH_VERSION=2.10.1
RUN case "${TARGETARCH}" in \
        amd64) monolith_arch=x86_64 ;; \
        arm64) monolith_arch=aarch64 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/Y2Z/monolith/releases/download/v${MONOLITH_VERSION}/monolith-gnu-linux-${monolith_arch}" -o /usr/local/bin/monolith && \
    chmod +x /usr/local/bin/monolith

WORKDIR /app

# Install node modules
COPY carnivore-lib/carnivore/readability/package*.json carnivore-lib/carnivore/readability/
RUN cd carnivore-lib/carnivore/readability && npm install && npm cache clean --force

# Install Playwright and Chromium. (This is to avoid re-build this layer if carnivore-lib code has changed.)
RUN pip install playwright==1.48.0 && playwright install --with-deps chromium

# Install Bypass Paywalls Clean Chrome extension
ARG BYPASS_PAYWALLS_VERSION=master
RUN curl -fsSL https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-${BYPASS_PAYWALLS_VERSION}.zip -o /tmp/bypass-paywalls.zip && \
    mkdir -p /tmp/bypass-paywalls && \
    unzip /tmp/bypass-paywalls.zip -d /tmp/bypass-paywalls && \
    top_dir=$(find /tmp/bypass-paywalls -mindepth 1 -maxdepth 1 -type d) && \
    mv "$top_dir"/* /tmp/bypass-paywalls && \
    rmdir "$top_dir" && \
    mkdir -p /app/chrome-extensions && \
    mv /tmp/bypass-paywalls /app/chrome-extensions/bypass-paywalls && \
    rm -rf /tmp/bypass-paywalls /tmp/bypass-paywalls.zip
ENV CARNIVORE_CHROME_EXTENSION_PATHS=/app/chrome-extensions/bypass-paywalls

# Install Python packages
COPY applications/telegram-bot/requirements.txt applications/telegram-bot/
COPY post-process/requirements.txt post-process/
RUN pip install --upgrade pip && pip install --no-cache-dir -r applications/telegram-bot/requirements.txt -r post-process/requirements.txt

# Copy code and install carnivore-lib
COPY carnivore-lib/ carnivore-lib/
RUN pip install -e carnivore-lib
COPY applications/ applications/
COPY post-process/ post-process/
COPY entrypoint.sh .

ENTRYPOINT [ "./entrypoint.sh" ]
