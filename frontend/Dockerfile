# Development image: runs the Vite dev server (see docker-compose.yml).
# A production build served by a web server is added in Phase 9.
FROM node:22-alpine

RUN mkdir /app && chown node:node /app
WORKDIR /app
USER node

COPY --chown=node:node package.json package-lock.json ./
RUN npm ci && sha256sum package-lock.json | awk '{print $1}' > node_modules/.package-lock.sha256

COPY --chown=node:node . .

EXPOSE 5173

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD wget -qO /dev/null http://127.0.0.1:5173/ || exit 1

CMD ["sh", "-c", "LOCK_HASH=$(sha256sum package-lock.json | awk '{print $1}'); STORED_HASH=$(cat node_modules/.package-lock.sha256 2>/dev/null || true); if [ \"$LOCK_HASH\" != \"$STORED_HASH\" ]; then echo 'package-lock.json changed; refreshing frontend dependencies...'; npm ci && echo \"$LOCK_HASH\" > node_modules/.package-lock.sha256; fi; exec npm run dev -- --host 0.0.0.0"]
