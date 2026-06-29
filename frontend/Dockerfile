# ===== Stage 1: Build React =====
FROM node:24-alpine AS build

WORKDIR /app

# Copy package files trước để cache npm install
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build React
RUN npm run build

# ===== Stage 2: Serve bằng Nginx =====
FROM nginx:alpine

# Copy build output
COPY --from=build /app/build /usr/share/nginx/html

# Write our config as the main nginx.conf so Instana agent can find stub_status
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 8080

CMD ["nginx", "-g", "daemon off;"]
