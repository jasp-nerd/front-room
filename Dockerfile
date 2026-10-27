# One container for a Front Room deployment: the room server, which also serves the built web app.
#
#   az acr build -r <registry> -t front-room:<tag> .

# --- The web app -----------------------------------------------------------------------------------
FROM node:22.20-bookworm-slim AS web
WORKDIR /src
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/web/package.json apps/web/
COPY packages/design/package.json packages/design/
COPY packages/protocol/package.json packages/protocol/
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY packages packages
RUN pnpm --filter @frontroom/design build && pnpm --filter @frontroom/web build

# --- The room server ---------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY agents agents
COPY engine/pyproject.toml engine/
RUN mkdir -p engine/frontroom_engine && touch engine/frontroom_engine/__init__.py \
    && uv sync --frozen --no-dev --package frontroom-agents
COPY --from=web /src/apps/web/dist /app/web
ENV FRONTROOM_WEB_DIST=/app/web PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
USER nobody
CMD ["uvicorn", "frontroom_agents.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
