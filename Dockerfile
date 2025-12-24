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

# Copy application code
COPY unredactor_mcp/ ./unredactor_mcp/

# Expose port
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Run the server
CMD ["python", "-m", "unredactor_mcp.server"]
