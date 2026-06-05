# Dockerfile for Railway Deployment
# Automated UK Job Application Pipeline

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
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

# Run the pipeline
CMD ["python3", "job_pipeline.py"]
