# Dockerfile
# ==========
# YEH FILE KYA KARTI HAI:
# Container image banati hai deployment ke liye
# Render/Railway/Fly pe deploy karne ke liye use karo

# Python 3.11 slim image use karo (lightweight)
FROM python:3.11-slim

# Working directory set karo
WORKDIR /app

# Dependencies pehle install karo (Docker cache optimization)
# requirements.txt pehle copy karo, phir code
COPY requirements.txt .

# Dependencies install karo
RUN pip install --no-cache-dir -r requirements.txt

# Saara code copy karo
COPY . .

# Catalog directory banao
RUN mkdir -p catalog

# Catalog JSON banao
RUN python -c "from catalog.scraper import SHL_CATALOG, save_catalog; save_catalog(SHL_CATALOG)"

# Port expose karo
EXPOSE 8000

# Health check (Docker ke liye)
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# App start karo
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]