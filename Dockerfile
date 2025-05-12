# Use an official Python runtime as the base image
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

# Set work directory
WORKDIR /app

# Install system dependencies required for wkhtmltopdf (needed for pdfkit)
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_HTTP_TIMEOUT=60
# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for logs if they don't exist
RUN mkdir -p system_log reports

# Expose port
EXPOSE 3333

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3333"]