FROM python:3.13.0

ENV NODE_ENV=production

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm pandoc jq curl && rm -rf /var/lib/apt/lists/*
RUN curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"
RUN cargo install monolith

WORKDIR /app

# Install node modules
COPY carnivore/app/readability/package*.json carnivore/app/readability/
RUN cd carnivore/app/readability && npm install && npm cache clean --force

# Install Python packages
COPY carnivore/requirements.txt carnivore/
COPY telegram-bot/requirements.txt telegram-bot/
COPY post-process/requirements.txt post-process/
RUN pip install --upgrade pip && pip install --no-cache-dir -r carnivore/requirements.txt -r telegram-bot/requirements.txt -r post-process/requirements.txt
# Install browser
RUN playwright install firefox

COPY carnivore/app/readability/index.mjs carnivore/app/readability/
COPY carnivore/app/main.py carnivore/app/
COPY telegram-bot/app/main.py telegram-bot/app/
COPY post-process/ post-process/
COPY entrypoint.sh .

ENTRYPOINT [ "./entrypoint.sh" ]
