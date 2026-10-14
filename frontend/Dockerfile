# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Unprivileged nginx: runs as a non-root user and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine
# Pull OS security fixes newer than the base image (Trivy found 41 HIGH/CRITICAL without this).
USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# The base image already runs as the unprivileged nginx user (uid 101); say so explicitly.
USER 101
EXPOSE 8080
