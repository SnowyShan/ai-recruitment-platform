# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# VITE_API_URL and VITE_INTERVIEW_URL injected at build time via --build-arg
ARG VITE_API_URL
ARG VITE_INTERVIEW_API_URL
ARG VITE_INTERVIEW_URL
ARG VITE_BYPASS_CAPTCHA=false

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_INTERVIEW_API_URL=$VITE_INTERVIEW_API_URL
ENV VITE_INTERVIEW_URL=$VITE_INTERVIEW_URL
ENV VITE_BYPASS_CAPTCHA=$VITE_BYPASS_CAPTCHA

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config: serve SPA with fallback to index.html for client-side routing
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
