FROM python:3.11-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements-mcp.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-mcp.txt

# Set environment variables BEFORE copying code
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Copy application code (v2 - force rebuild)
COPY unredactor_mcp/ ./unredactor_mcp/

# Test that import works during build
RUN python -c "from unredactor_mcp.server import app; print('Build test: app imported successfully')"

# Expose port
EXPOSE 8080

# Run the server - use shell form to expand $PORT
CMD python -c "import os; print('Starting...'); port=int(os.environ.get('PORT',8080)); print(f'Port: {port}'); from unredactor_mcp.server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=port)"
