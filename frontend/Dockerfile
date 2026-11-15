FROM oven/bun:1.4.2 AS build
WORKDIR /app
COPY package.json bun.lock ./
COPY frontend/package.json frontend/
COPY packages/ui/package.json packages/ui/
RUN bun install --frozen-lockfile --filter service-unavailable-workbench
COPY frontend/ frontend/
COPY packages/ui/src packages/ui/src
WORKDIR /app/frontend
RUN bun --bun run build

FROM oven/bun:1.4.2-slim AS runtime
WORKDIR /app
COPY package.json bun.lock ./
COPY frontend/package.json frontend/
COPY packages/ui/package.json packages/ui/
RUN bun install --frozen-lockfile --production --filter service-unavailable-workbench
COPY --from=build /app/frontend/build frontend/build
COPY --from=build /app/packages/ui/src packages/ui/src
WORKDIR /app/frontend
ENV HOST=0.0.0.0
EXPOSE 3000
USER bun
CMD ["bun", "build/index.js"]
