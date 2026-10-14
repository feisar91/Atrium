---
title: Install Atrium
description: Install Atrium with Docker Compose in a few minutes.
---

# Install Atrium

Docker Compose, published images, no build step. Takes a few minutes.

::: tip Requirements
Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose (bundled with Docker Desktop and modern Docker Engine installs).
:::

## 1. Clone the repo

```sh
git clone https://github.com/feisar91/Atrium.git
cd Atrium
```

## 2. Configure your environment

Copy the example env file and fill in the required values - each has a one-line command to generate it.

```sh
cp backend/.env.example backend/.env
```

At minimum, `backend/.env` needs:

```sh
SECRET_KEY=...          # python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=...      # python3 -c "import secrets; print(secrets.token_hex(32))"
POSTGRES_PASSWORD=...   # python3 -c "import secrets; print(secrets.token_urlsafe(24))"
ENCRYPTION_KEY=...      # python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

::: tip Behind another reverse proxy?
If Atrium will sit behind another reverse proxy (Caddy, Traefik, a cloud load balancer) rather than facing the internet directly, also set `TRUSTED_PROXY_CIDR` to that proxy's address so guest IPs are logged correctly instead of the proxy's own.
:::

## 3. Start the stack

This pulls the published backend and web images and brings up Postgres alongside them.

```sh
docker compose up -d
```

## 4. Finish setup in the browser

Open `http://localhost/admin/`. You'll land on the first-run setup wizard to create your superadmin account - or restore from an existing Atrium backup, if you have one.

## 5. Point UniFi at it

In the UniFi controller: **Client Devices → Hotspot → Landing Page**, and enter this server's address.

---

Building from source, contributing, or want hot-reload for frontend work instead? See [DEVELOPMENT.md](https://github.com/feisar91/Atrium/blob/main/DEVELOPMENT.md).
