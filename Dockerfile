FROM python:3.13.0-alpine3.20

ENV NODE_ENV=production

# Install node.js
RUN apk add --no-cache nodejs npm

# Install pandoc
RUN apk add --no-cache pandoc

WORKDIR /app

# Install node.js dependencies
COPY app/readability/package*.json readability/
RUN cd readability && npm install
RUN cd readability && rm package*.json

COPY app/main.py .
COPY app/readability/index.mjs readability/

ENTRYPOINT [ "python", "main.py" ]
