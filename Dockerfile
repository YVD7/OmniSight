FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and enable stdout buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# Install system dependencies including git for auto-cloning target repos and libpq for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright Chromium browser & system dependencies
RUN python -m playwright install --with-deps chromium

# Copy application source code
COPY . .

# Expose Gateway API port
EXPOSE 8000

# Start Gateway API server using api.getway_api:app
CMD ["uvicorn", "api.getway_api:app", "--host", "0.0.0.0", "--port", "8000"]
