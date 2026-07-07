FROM node:24-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm@10.26.1

WORKDIR /repo

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY lib ./lib
COPY artifacts/api-server ./artifacts/api-server

RUN pnpm install --frozen-lockfile

RUN python3 -m venv /repo/.pyvenv \
    && /repo/.pyvenv/bin/pip install --no-cache-dir -r artifacts/api-server/requirements.txt

ENV PYTHON_BIN=/repo/.pyvenv/bin/python3

RUN pnpm --filter @workspace/api-spec run codegen || true
RUN pnpm --filter @workspace/api-server run build

ENV NODE_ENV=production
EXPOSE 8080
ENV PORT=8080

CMD ["node", "--enable-source-maps", "artifacts/api-server/dist/index.mjs"]
