FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    gosu \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    default-mysql-client postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Vulnerability scanning tools (run against domains, not from inside the host).
# Each download is best-effort so a transient release URL change never breaks the build;
# the scanner detects tool availability at runtime and degrades gracefully.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nmap hydra wget unzip tar \
    && rm -rf /var/lib/apt/lists/* \
    && ARCH="$(dpkg --print-architecture)" \
    && NUCLEI_VER=3.3.7 \
    && GOBUSTER_VER=3.6.0 \
    && case "$ARCH" in amd64) GBARCH=x86_64 ;; arm64) GBARCH=arm64 ;; *) GBARCH=x86_64 ;; esac \
    && ( wget -qO /tmp/nuclei.zip "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VER}/nuclei_${NUCLEI_VER}_linux_${ARCH}.zip" \
         && unzip -o /tmp/nuclei.zip -d /usr/local/bin nuclei \
         && chmod +x /usr/local/bin/nuclei || echo "nuclei install skipped" ) \
    && ( wget -qO /tmp/gobuster.tar.gz "https://github.com/OJ/gobuster/releases/download/v${GOBUSTER_VER}/gobuster_Linux_${GBARCH}.tar.gz" \
         && tar -xzf /tmp/gobuster.tar.gz -C /usr/local/bin gobuster \
         && chmod +x /usr/local/bin/gobuster || echo "gobuster install skipped" ) \
    && rm -f /tmp/nuclei.zip /tmp/gobuster.tar.gz

# WPScan (WordPress scanner) — best-effort Ruby gem install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ruby ruby-dev build-essential libcurl4-openssl-dev \
    && ( gem install wpscan --no-document || echo "wpscan install skipped" ) \
    && apt-get purge -y build-essential ruby-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM base AS runtime

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY alembic.ini .
COPY alembic ./alembic
COPY src ./src

RUN addgroup --system --gid 1000 controlbox \
    && adduser --system --uid 1000 --ingroup controlbox controlbox \
    && mkdir -p /var/lib/controlbox/sites /var/lib/controlbox/backups/databases /var/lib/controlbox/backups \
    && chown -R controlbox:controlbox /var/lib/controlbox /app

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["sh", "-c", "uvicorn controlbox.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]
