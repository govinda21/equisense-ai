# Frontend build stage
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

# Backend stage
FROM python:3.11-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip setuptools wheel && pip install -e .[dev]
COPY . .
# Copy frontend build
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
RUN python -m playwright install --with-deps chromium
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
