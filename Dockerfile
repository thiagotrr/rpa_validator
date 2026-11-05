# syntax=docker/dockerfile:1
# Estágio "sistema": Python + LibreOffice (texto nativo do Word) + Tesseract (OCR) + poppler (PDF -> imagem).
# É a camada pesada e a que menos muda: fica primeiro para o cache do Docker funcionar.
FROM python:3.12-slim-bookworm AS sistema
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer-nogui tesseract-ocr tesseract-ocr-por poppler-utils fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Estágio "testes": + dependências de desenvolvimento. O código entra por volume (docker-compose.yml).
FROM sistema AS testes
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir ".[dev]"
CMD ["pytest", "-q"]
