# Dockerfile for Railway Deployment
# FastAPI Web Server for Job Pipeline

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .
COPY *.sh .
COPY *.sql .

# Make scripts executable
RUN chmod +x *.py *.sh 2>/dev/null || true

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port (Railway will use dynamic port)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run FastAPI server (Railway's startCommand in railway.json will override this)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
