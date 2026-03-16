FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to prevent pip from pulling GPU version
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    torchvision==0.17.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies one group at a time
RUN pip install --no-cache-dir sentence-transformers==2.3.1
RUN pip install --no-cache-dir chromadb==0.5.23
RUN pip install --no-cache-dir python-telegram-bot==20.7 httpx==0.25.2
RUN pip install --no-cache-dir google-generativeai==0.8.3
RUN pip install --no-cache-dir gspread==6.0.2 google-auth==2.28.0 google-auth-oauthlib==1.2.0
RUN pip install --no-cache-dir fastapi==0.109.2 uvicorn==0.27.1
RUN pip install --no-cache-dir python-dotenv==1.0.1 twilio==8.12.0

# Copy app code
COPY . .

CMD ["python", "bot_telegram.py"]