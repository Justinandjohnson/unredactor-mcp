# Unredactor MCP

[![PyPI version](https://badge.fury.io/py/unredactor-mcp.svg)](https://badge.fury.io/py/unredactor-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that lets AI assistants detect and replace black redaction boxes in PDF documents.

## What it does

This tool helps you **write over** redaction boxes in PDFs - like white-out for digital documents.

- **Detect** black redaction boxes on any PDF page
- **Replace** boxes of specific dimensions with custom text
- **Process** entire documents or specific pages

> **Note**: This tool does NOT "recover" redacted data. It simply replaces black boxes with white boxes containing your text.

## Installation

### Option 1: Remote Server (Easiest)

Add to your Claude Desktop or Claude Code config:

```json
{
  "mcpServers": {
    "unredactor": {
      "url": "https://unredactor-mcp.up.railway.app/mcp"
    }
  }
}
```

### Option 2: Install via pip

```bash
pip install unredactor-mcp
```

Then add to your config:

```json
{
  "mcpServers": {
    "unredactor": {
      "command": "unredactor-mcp"
    }
  }
}
```

### Option 3: Docker

```bash
docker pull jjohnson/unredactor-mcp
```

```json
{
  "mcpServers": {
    "unredactor": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "jjohnson/unredactor-mcp"]
    }
  }
}
```

### Option 4: From Source

```bash
git clone https://github.com/Justinandjohnson/unredactor-mcp
cd unredactor-mcp
pip install -e .
```

## Available Tools

| Tool | Description |
|------|-------------|
| `upload_pdf` | Upload a PDF (base64-encoded) for processing |
| `get_pdf_info` | Get page count and dimensions |
| `detect_black_boxes` | Find redaction boxes on a specific page |
| `detect_all_pages` | Scan entire PDF for boxes |
| `replace_redaction_boxes` | Replace boxes of a specific size with text |
| `download_pdf` | Get the modified PDF (base64-encoded) |
| `cleanup_file` | Delete temporary files |

## Usage Example

Once configured, you can ask Claude:

1. "Upload this PDF and scan it for redaction boxes"
2. "Replace all the 100x20 boxes on page 1 with 'CLASSIFIED'"
3. "Download the modified PDF"

## GUI Application

A standalone GUI application is also available for manual editing:

```bash
pip install PyMuPDF pillow opencv-python
python unredact.py
```

<img width="976" alt="GUI Screenshot" src="https://github.com/user-attachments/assets/b7628f39-7115-4b4f-bd9c-f2977650501e" />

## Legal Disclaimer

- This tool is for forensics and legitimate document editing purposes only
- It does NOT recover truly destroyed/redacted data
- **Republishing altered documents may be illegal**
- By using this tool, you assume all legal liability

## Known Limitations

- Converts PDF pages to PNG and back, which can increase file size
- Font size remains constant, so text may appear smaller after multiple edits
- Best results with clear, rectangular black boxes

## License

MIT License - see [LICENSE](LICENSE) for details.
