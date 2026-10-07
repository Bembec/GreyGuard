FROM node:22-alpine AS build
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
COPY sdk/javascript /app/sdk/javascript

RUN npm run build

FROM nginx:1.31.6-alpine3.24-slim
RUN apk upgrade --no-cache
COPY deployment/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz
