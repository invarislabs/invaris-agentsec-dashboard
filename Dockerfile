FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

# AgentSec supplies the report logic (agentsec.dashboard, agentsec.verdicts). Override with
# --build-arg AGENTSEC_REQUIREMENT="..." to test another engine build.
ARG AGENTSEC_REQUIREMENT="invaris-agentsec==0.9.0"
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
 && pip install "$AGENTSEC_REQUIREMENT"

COPY pyproject.toml LICENSE NOTICE ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install . && useradd --system --uid 10001 app
USER app

EXPOSE 8000
# Apply migrations, then serve. Behind a TLS-terminating proxy (Render, a load balancer). $PORT is set by the host.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
