# ── Build stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools needed by faiss-cpu / sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# calypsoai is not on PyPI — bundle the wheel locally under vendor/
COPY vendor/calypsoai-2.82.0-py3-none-any.whl .

# Install torch CPU-only first to avoid pulling the full CUDA stack (~2 GB)
RUN pip install --no-cache-dir --prefix=/install \
        torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies (including gunicorn) into the same prefix
RUN pip install --no-cache-dir --prefix=/install \
        gunicorn \
        calypsoai-2.82.0-py3-none-any.whl \
        -r requirements.txt

# Pre-download the sentence-transformer model so it's baked into the image
# (avoids a slow cold-start on every container launch)
# PYTHONPATH must include /install/lib so the just-installed packages are importable
RUN PYTHONPATH=/install/lib/python3.11/site-packages \
    SENTENCE_TRANSFORMERS_HOME=/install/model-cache \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages and pre-downloaded model from builder
COPY --from=builder /install /usr/local

# Set the model cache path so sentence-transformers finds it at runtime
ENV SENTENCE_TRANSFORMERS_HOME=/usr/local/model-cache \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a non-root user
RUN useradd --no-create-home --shell /bin/false appuser

# Copy application source
COPY app.py settings.py rag_engine.py rag.txt ./
COPY templates/ templates/
COPY static/ static/

# Ensure the uploads directory exists and is writable by appuser
RUN mkdir -p uploads && chown -R appuser:appuser /app

USER appuser

EXPOSE 8800

# Gunicorn: 1 worker is sufficient for a demo; adjust -w as needed
CMD ["gunicorn", "--bind", "0.0.0.0:8800", "--workers", "1", "--timeout", "120", "app:app"]
