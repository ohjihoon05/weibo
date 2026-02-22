FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/

# Create data directories
RUN mkdir -p data/posts data/history data/images data/logs

ENTRYPOINT ["python", "-m", "src.main"]
