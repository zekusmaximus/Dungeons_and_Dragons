# Stage 1: build the UI
FROM node:20-alpine AS ui-builder
WORKDIR /app/ui

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY ui/package*.json ./
COPY ui/tsconfig.json ./tsconfig.json
COPY ui/vite.config.ts ./vite.config.ts
COPY ui/src ./src
COPY ui/public ./public

RUN npm install
RUN npm run build

# Stage 2: runtime image
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV DM_SERVICE_REPO_ROOT=/app
ENV STORAGE_BACKEND=sqlite
ENV SQLITE_PATH=/data/dm.sqlite

RUN mkdir -p /data
COPY service/requirements.txt /app/service/requirements.txt
RUN pip install --no-cache-dir -r /app/service/requirements.txt

COPY service /app/service
COPY dice /app/dice
COPY data /app/data
COPY worlds /app/worlds
COPY schemas /app/schemas
COPY sessions /app/sessions
COPY PROMPTS /app/PROMPTS
COPY ui/dist /app/ui/dist
COPY docs /app/docs
COPY README.md /app/README.md
COPY MIGRATION.md /app/MIGRATION.md

EXPOSE 8000
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
