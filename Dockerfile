FROM python:3.13.0-alpine3.20

ENV NODE_ENV=production

# Install node.js
RUN apk add --no-cache nodejs npm

# Install pandoc
RUN apk add --no-cache pandoc

WORKDIR /app

COPY app/readability/package*.json readability/
RUN cd readability && npm install

COPY app/ .

ENTRYPOINT [ "python", "main.py" ]
