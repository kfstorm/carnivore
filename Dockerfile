FROM rust:1.82.0-bookworm AS monolith_builder

ARG MONOLITH_VERSION=2.8.3
RUN curl -fsSL "https://github.com/Y2Z/monolith/archive/refs/tags/v${MONOLITH_VERSION}.zip" -o /tmp/monolith.zip && \
    mkdir -p /tmp/monolith && \
    unzip /tmp/monolith.zip -d /tmp/monolith && \
    cd /tmp/monolith/monolith-${MONOLITH_VERSION} && \
    make install && \
    rm -rf /tmp/monolith /tmp/monolith.zip

FROM python:3.13.0-slim

ENV NODE_ENV=production

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    jq \
    curl \
    && rm -rf /var/lib/apt/lists/*
ARG PANDOC_VERSION=3.5
RUN curl -fsSL "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-$(dpkg --print-architecture).tar.gz" -o pandoc.tar.gz && \
    tar -xzf pandoc.tar.gz -C /usr/local --strip-components 1 && \
    rm pandoc.tar.gz
COPY --from=monolith_builder /usr/local/cargo/bin/monolith /usr/local/bin/monolith

WORKDIR /app

# Install node modules
COPY carnivore/app/readability/package*.json carnivore/app/readability/
RUN cd carnivore/app/readability && npm install && npm cache clean --force

# Install Python packages
COPY carnivore/requirements.txt carnivore/
COPY applications/telegram-bot/requirements.txt applications/telegram-bot/
COPY post-process/requirements.txt post-process/
RUN pip install --upgrade pip && pip install --no-cache-dir -r carnivore/requirements.txt -r applications/telegram-bot/requirements.txt -r post-process/requirements.txt

# Install browser
RUN playwright install firefox && playwright install-deps firefox && rm -rf /var/lib/apt/lists/*

COPY common/ common/
COPY carnivore/ carnivore/
COPY applications/ applications/
COPY post-process/ post-process/
COPY entrypoint.sh .

ENTRYPOINT [ "./entrypoint.sh" ]
