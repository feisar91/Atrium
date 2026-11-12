FROM python:3.12-slim

ARG APP_VERSION=0.0.0-dev
ENV APP_VERSION=${APP_VERSION}

WORKDIR /app

# Pick up Debian security fixes newer than the base image. No build
# toolchain or libpq-dev: every dependency ships a wheel (psycopg2-binary
# bundles its own libpq), and leaving them out keeps gcc and libpq's
# Kerberos stack out of the runtime image.
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir --only-binary=:all: -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 5000

CMD ["./entrypoint.sh"]
