# Shared base image for both the API server and the render worker — they
# need the exact same Manim/Cairo/Pango system dependencies, so building
# one image and selecting the process via CMD/entrypoint avoids drift
# between what the API container and worker container can render (which
# would otherwise show up as "works when I render locally, fails in
# prod" bugs).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    libgl1 \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/ ./packages/
COPY manim_engine/ ./manim_engine/
COPY workers/ ./workers/
COPY apps/ ./apps/
COPY debug_cli/ ./debug_cli/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default: run the API. docker-compose.yml overrides `command:` for the
# worker service to run celery instead.
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
