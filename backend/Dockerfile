# GEDS backend container — Python 3.11 slim, ~250 MB final image.
# Works on Render, Fly.io, Hugging Face Spaces, Google Cloud Run, etc.

FROM python:3.11-slim

WORKDIR /app

# System deps required by scipy/numpy wheels (libstdc++, libgomp).
# blis (spaCy dep) needs gcc on some architectures; slim image ships it via build-essential.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so changes to app code don't bust the layer cache.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

# Now copy the rest of the project.
COPY . .

# Render/Fly inject $PORT at runtime; default to 8000 for local docker run.
ENV PORT=8000
EXPOSE 8000

# Bind to 0.0.0.0 (not localhost) so the container is reachable externally.
# Single worker is fine — engine is CPU-bound and Monte Carlo is already vectorized.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
