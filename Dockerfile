FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-build the ChromaDB knowledge base at container build time
RUN python -c "from src.rag_pipeline import build_kb; build_kb()"

# Default: run Telegram bot
# Override CMD in Railway/Render for WhatsApp: uvicorn bot_whatsapp:app --host 0.0.0.0 --port $PORT
CMD ["python", "bot_telegram.py"]
