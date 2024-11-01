FROM python:3.13.0-alpine3.20

ENV NODE_ENV=production

# Install dependencies
RUN apk add --no-cache bash nodejs npm pandoc monolith jq curl

WORKDIR /app

# Install node modules
COPY carnivore/app/readability/package*.json carnivore/app/readability/
RUN cd carnivore/app/readability && npm install && npm cache clean --force

# Install Python packages
COPY telegram-bot/requirements.txt telegram-bot/
COPY post-process/requirements.txt post-process/
RUN pip install --no-cache-dir -r telegram-bot/requirements.txt -r post-process/requirements.txt

COPY carnivore/app/readability/index.mjs carnivore/app/readability/
COPY carnivore/app/main.py carnivore/app/
COPY telegram-bot/app/main.py telegram-bot/app/
COPY post-process/ post-process/
COPY entrypoint.sh .

ENTRYPOINT [ "./entrypoint.sh" ]
