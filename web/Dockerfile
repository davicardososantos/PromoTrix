# syntax=docker/dockerfile:1
# Mesmo desenho do Fintrix: deps → builder (build standalone) → runner enxuto.

FROM node:22-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat openssl
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
RUN apk add --no-cache openssl
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npx prisma generate
RUN npm run build
# Pasta do banco SQLite (volume). Dona = uid 1001, o mesmo usuário que roda o app e as migrations.
RUN mkdir -p /data && chown 1001:1001 /data

# As migrations rodam no serviço `migrate` (docker-compose), a partir do estágio builder, que tem o
# node_modules completo que o CLI do Prisma precisa.
FROM node:22-alpine AS runner
WORKDIR /app
RUN apk add --no-cache openssl
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs \
  && mkdir -p /data && chown nextjs:nodejs /data

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Query engine do Prisma (o standalone não copia sozinho)
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/.prisma ./node_modules/.prisma

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
