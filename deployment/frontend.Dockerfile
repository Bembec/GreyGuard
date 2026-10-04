FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci
WORKDIR /app
COPY frontend ./frontend
COPY sdk/javascript ./sdk/javascript
WORKDIR /app/frontend
RUN npm run build
FROM nginx:1.27-alpine
COPY deployment/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
