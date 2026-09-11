# Partie 16 (bis) -- real containerization for the Next.js frontend,
# previously missing entirely (this repo had no frontend Dockerfile at
# all before self-hosted packaging needed one).

FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app appuser
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
RUN chown -R appuser:app /app
USER appuser
EXPOSE 3000
CMD ["npm", "start"]
