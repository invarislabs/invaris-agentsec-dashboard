FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

# AgentSec supplies the report logic. agentsec.dashboard first ships in AgentSec 0.9.0; until that release the
# default pins the add-dashboard commit CI tests against (a commit, so it keeps working after the branch is merged).
# Override with --build-arg AGENTSEC_REQUIREMENT="...".
ARG AGENTSEC_REQUIREMENT="invaris-agentsec @ git+https://github.com/invarislabs/invaris-agentsec.git@15f909e615b765b906af00504e0c4959f8fe342f"
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
 && pip install "$AGENTSEC_REQUIREMENT"

COPY pyproject.toml LICENSE NOTICE ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install . && useradd --system --uid 10001 app
USER app

EXPOSE 8000
# Apply migrations, then serve. Behind a TLS-terminating proxy (Fly, Render, Railway, a load balancer).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
