FROM python:3.13.0-alpine3.20

ENV NODE_ENV=production

# Install dependencies
RUN apk add --no-cache nodejs npm pandoc monolith

WORKDIR /app

# Install node modules
COPY markclipper/app/readability/package*.json markclipper/app/readability/
RUN cd markclipper/app/readability && npm install

# Install Python packages
COPY telegram-bot/requirements.txt telegram-bot/
RUN cd telegram-bot && pip install --no-cache-dir -r requirements.txt

COPY markclipper/app/readability/index.mjs markclipper/app/readability/
COPY markclipper/app/main.py markclipper/app/
COPY telegram-bot/app/main.py telegram-bot/app/

ENTRYPOINT [ "sh", "-c", "python telegram-bot/app/main.py --token \"${TELEGRAM_TOKEN}\" --channel-id \"${TELEGRAM_CHANNEL_ID}\" --output-dir \"${OUTPUT_DIR}\"" ]
