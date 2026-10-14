# One image for the whole app: the API (FastAPI + models) also serves the built web UI.
#   docker build -t vn-alpr . && docker run -p 8080:8080 vn-alpr      ->  http://localhost:8080
# Cloud Run: gcloud run deploy --source .  (see README, "Deploy")

# ---- web UI ----------------------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# UI and API share one origin in this image: calls go to /parking/... (in development Vite proxies /api/...)
RUN VITE_API_URL= npm run build

# ---- API -------------------------------------------------------------------------------------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app \
    ALPR_WEB_DIR=/app/web/dist \
    ALPR_PRELOAD=1 \
    PORT=8080
# libGL/glib for OpenCV (ultralytics pulls the non-headless build)
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# CPU-only torch keeps the image small; use an nvidia/cuda base image for GPU inference.
# torchvision must come from the same index: the PyPI one that ultralytics would pull is built for another torch
# ("operator torchvision::nms does not exist")
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements-serve.txt .
RUN pip install -r requirements-serve.txt

COPY src ./src
COPY app ./app
COPY configs ./configs
COPY models ./models
COPY --from=web /web/dist ./web/dist

EXPOSE 8080
# Cloud Run sets PORT; one worker: the SQLite file and the demo clock live in this process
CMD ["sh", "-c", "exec uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
