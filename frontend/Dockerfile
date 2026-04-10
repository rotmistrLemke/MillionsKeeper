# ── Stage 1: builder ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Зависимости (кэшируем отдельным слоем)
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# Исходный код
COPY . .

# Сборка React SPA
RUN npm run build

# ── Stage 2: nginx static server ─────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Кастомный nginx конфиг
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Собранный SPA
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
