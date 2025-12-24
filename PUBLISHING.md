# Publishing Checklist for Unredactor MCP

## ✅ Completed

- [x] GitHub repository created: https://github.com/Justinandjohnson/unredactor-mcp
- [x] Railway deployment successful: https://unredactor-mcp-production.up.railway.app
- [x] Python package built (ready for PyPI): `dist/unredactor_mcp-0.1.0*`
- [x] Docker image ready (needs push to Docker Hub)
- [x] smithery.yaml configured

## 📋 Remaining Tasks

### 1. Publish to PyPI

**Requirements:**
- PyPI API token (get from https://pypi.org/manage/account/token/)

**Steps:**
```bash
# Install twine if not already installed
pip install twine

# Upload to PyPI (will prompt for token)
twine upload dist/*
```

**Result:** Package will be available at https://pypi.org/project/unredactor-mcp/

---

### 2. Publish to Docker Hub

**Requirements:**
- Docker Hub account login

**Steps:**
```bash
# Login to Docker Hub
docker login

# Build the image
docker build -t justinandjohnson/unredactor-mcp:latest .
docker build -t justinandjohnson/unredactor-mcp:0.1.0 .

# Push to Docker Hub
docker push justinandjohnson/unredactor-mcp:latest
docker push justinandjohnson/unredactor-mcp:0.1.0
```

**Result:** Image will be available at https://hub.docker.com/r/justinandjohnson/unredactor-mcp

---

### 3. Submit to Smithery

**Requirements:**
- Smithery account at https://smithery.ai

**Steps:**
1. Go to https://smithery.ai
2. Sign up / Log in
3. Submit your MCP server (point to GitHub repo)
4. Smithery will use the `smithery.yaml` file from the repo

**Repository URL to provide:** https://github.com/Justinandjohnson/unredactor-mcp

**Result:** Server will be installable via:
```bash
npx -y @smithery/cli install unredactor-mcp
```

---

### 4. Submit to Glama

**Requirements:**
- Glama account at https://glama.ai

**Steps:**
1. Go to https://glama.ai
2. Sign up / Log in
3. Submit MCP server through their submission form
4. Provide GitHub repository URL

**Repository URL to provide:** https://github.com/Justinandjohnson/unredactor-mcp

**Result:** Server will be listed in Glama's MCP directory

---

### 5. MCP Registry

**Note:** The official MCP Registry at https://registry.modelcontextprotocol.io/ likely aggregates servers from Smithery and Glama automatically. Once published to those platforms, the server should appear in the registry.

---

## 📝 Server Information

**Name:** Unredactor MCP
**Description:** A Model Context Protocol server for detecting and replacing black redaction boxes in PDF documents
**GitHub:** https://github.com/Justinandjohnson/unredactor-mcp
**Railway URL:** https://unredactor-mcp-production.up.railway.app
**License:** MIT

**Installation Options:**
- PyPI: `pip install unredactor-mcp`
- Docker: `docker pull justinandjohnson/unredactor-mcp`
- HTTP: Connect to `https://unredactor-mcp-production.up.railway.app/mcp`
- Smithery: `npx @smithery/cli install unredactor-mcp`

**Tools Provided:**
- `upload_pdf` - Upload PDF for processing
- `get_pdf_info` - Get page count and dimensions
- `detect_black_boxes` - Find redaction boxes on a page
- `detect_all_pages` - Scan entire PDF
- `replace_redaction_boxes` - Replace boxes with text
- `download_pdf` - Download modified PDF
- `cleanup_file` - Delete temporary files

---

## 🔧 Quick Commands Reference

```bash
# Publish to PyPI
twine upload dist/*

# Publish to Docker Hub
docker login
docker build -t justinandjohnson/unredactor-mcp:latest .
docker push justinandjohnson/unredactor-mcp:latest

# Test the Railway deployment
curl https://unredactor-mcp-production.up.railway.app/health

# Test the MCP endpoint
curl -X POST https://unredactor-mcp-production.up.railway.app/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
```
