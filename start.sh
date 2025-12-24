#!/bin/bash
set -e

echo "=== Unredactor MCP Startup ==="
echo "PORT=${PORT:-8080}"

# Use default port if not set
PORT=${PORT:-8080}

echo "Testing Python import..."
python -c "from unredactor_mcp.server import app; print('Import OK:', app)"

echo "Starting uvicorn on 0.0.0.0:$PORT..."
exec uvicorn unredactor_mcp.server:app --host 0.0.0.0 --port $PORT
