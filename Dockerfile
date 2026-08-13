# syntax=docker/dockerfile:1
#
# One image serves both the API and the built frontend from the same origin — no CORS, no
# second deploy, one URL (see decisions.md). Sized for a Hugging Face Space on Docker (free
# CPU tier): listens on 7860, runs as uid 1000, no GPU, no API key baked in.

# ---------- stage 1: build the React frontend ----------
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build          # -> /web/dist  (tsc + vite build)

# ---------- stage 2: the Python app ----------
FROM python:3.9-slim AS app

# docTR (via OpenCV) needs these shared libraries present at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run the container as uid 1000; make /app writable by it so the
# SQLite store (dedup + corrections) and any re-learned region can be written.
RUN useradd -m -u 1000 user && mkdir -p /app/data && chown -R user:user /app
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    HOME=/home/user \
    PYTHONUNBUFFERED=1
WORKDIR /app

# CPU-only PyTorch — the free tier has no GPU, and this keeps the image far smaller.
RUN pip install --user --no-cache-dir \
        torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user:user requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Bake the OCR model into the image so the first upload isn't a cold model download.
RUN python -c "from doctr.models import ocr_predictor; ocr_predictor(pretrained=True)"

# The code, the one region file the app loads at startup, and the built frontend.
COPY --chown=user:user api/ ./api/
COPY --chown=user:user data/region_amount_due_80.json ./data/region_amount_due_80.json
COPY --chown=user:user --from=web /web/dist ./web/dist

# No key is shipped: uploads use the visitor's own key, so keyless requests are refused.
# (ALLOW_STUB is intentionally unset — this is production.)
# Listen on $PORT if the host injects one (Cloud Run sets 8080), else 7860 (HF Spaces / local).
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
