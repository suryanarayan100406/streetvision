# Stage 1: Build Vite app
FROM node:20-alpine AS builder
WORKDIR /app
ARG VITE_GOOGLE_MAPS_API_KEY=
ARG VITE_MAPBOX_TOKEN=
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_WS_URL=http://localhost:8000
ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_URL=$VITE_WS_URL
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
