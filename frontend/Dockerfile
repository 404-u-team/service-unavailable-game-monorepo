FROM oven/bun:1.4.2 AS build
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
RUN bun --bun run build

FROM oven/bun:1.4.2-slim AS runtime
WORKDIR /app
COPY --from=build /app/build ./build
COPY --from=build /app/package.json /app/bun.lock ./
RUN bun install --frozen-lockfile --production
ENV HOST=0.0.0.0
EXPOSE 3000
USER bun
CMD ["bun", "build/index.js"]
