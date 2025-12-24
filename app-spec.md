# Unredactor ChatGPT App Spec

## Product Context
- **Name**: Unredactor
- **API Base**: https://unredactor-mcp-production.up.railway.app
- **Auth**: None (public API)
- **Purpose**: Detect and replace redaction boxes in PDF documents

## Value Proposition

### Know: PDF Redaction Intelligence
Provides document-specific analysis that ChatGPT lacks:
- Detects black rectangular regions (redaction boxes) in PDFs
- Extracts precise box dimensions and positions
- Analyzes page-by-page or entire documents
- Returns PDF metadata (page count, dimensions)

### Do: Document Transformation
Takes real actions on user documents:
- Replaces redaction boxes with white boxes containing text
- Processes PDFs to create modified versions
- Handles multi-page documents
- Supports selective replacement by box size

### Show: Visual PDF Comparison
Custom UI dramatically improves the experience:
- Side-by-side PDF viewer (original vs unredacted)
- Visual highlighting of detected redaction boxes
- Interactive box selection and replacement
- Drag-and-drop PDF upload
- Synchronized scrolling between views

## Golden Prompts

### Direct (should trigger)
1. "Use unredactor to find black boxes in this PDF"
2. "Unredact this document"
3. "Show me redactions in this file with unredactor"
4. "Replace the redaction boxes in this PDF"
5. "Analyze this PDF for redacted content using unredactor"

### Indirect (should trigger)
1. "Can you find what's hidden under the black boxes in this PDF?"
2. "This document has redacted sections, can you help me see them?"
3. "Remove the black rectangles from this PDF"
4. "What text is underneath these redactions?"
5. "Show me what's been censored in this document"

### Negative (should NOT trigger)
1. "Create a PDF with redactions" (creating, not analyzing)
2. "What does this PDF say?" (general reading, not redaction-specific)
3. "Convert this PDF to Word" (different tool entirely)

## Current Implementation Status

### Existing MCP Server
- ✅ Deployed at: https://unredactor-mcp-production.up.railway.app
- ✅ Python-based FastAPI server
- ✅ Working tools: get_pdf_info, detect_black_boxes, detect_all_pages, replace_redaction_boxes
- ⚠️ Needs verification against ChatGPT App requirements

### Required Additions
- [ ] Widget implementation (React-based PDF viewer)
- [ ] SSE transport verification
- [ ] Well-known endpoints (/.well-known/openai-apps-challenge)
- [ ] Privacy and Terms endpoints
- [ ] Proper tool annotations (readOnlyHint, destructiveHint, openWorldHint)
- [ ] Widget metadata in tool responses (_meta fields)

## Tools

### 1. upload_pdf
- **Purpose**: Upload PDF for analysis (accepts base64-encoded content)
- **Annotations**:
  - readOnlyHint: false (stores file)
  - destructiveHint: false
  - openWorldHint: false
- **Input Schema**:
  ```json
  {
    "pdf_base64": "string (required) - Base64-encoded PDF content",
    "filename": "string (optional) - Filename for reference"
  }
  ```
- **Output Structure**:
  ```json
  {
    "content": "PDF uploaded successfully. File ID: {file_id}, Pages: {page_count}",
    "structuredContent": {
      "file_id": "string",
      "filename": "string",
      "page_count": "number"
    },
    "_meta": {
      "widgetAccessible": true,
      "phase": "uploaded"
    }
  }
  ```

### 2. detect_black_boxes
- **Purpose**: Detect redaction boxes on a specific page
- **Annotations**:
  - readOnlyHint: true
  - destructiveHint: false
  - openWorldHint: false
- **Input Schema**:
  ```json
  {
    "file_id": "string (required) - File ID from upload_pdf",
    "page_number": "number (optional, default: 0) - Page to analyze (0-indexed)"
  }
  ```
- **Output Structure**:
  ```json
  {
    "content": "Found {total} redaction boxes on page {page_number}. Grouped by size: {summary}",
    "structuredContent": {
      "file_id": "string",
      "page_number": "number",
      "total_boxes_found": "number",
      "boxes_by_size": "[array of size groups]"
    },
    "_meta": {
      "widgetAccessible": true,
      "phase": "detection",
      "all_boxes": "[complete box data for widget]"
    }
  }
  ```
- **Widget Template**: `ui://widget/detection-results.html`

### 3. detect_all_pages
- **Purpose**: Detect redaction boxes across entire document
- **Annotations**:
  - readOnlyHint: true
  - destructiveHint: false
  - openWorldHint: false
- **Input Schema**:
  ```json
  {
    "file_id": "string (required) - File ID from upload_pdf"
  }
  ```
- **Output Structure**:
  ```json
  {
    "content": "Analyzed {page_count} pages, found {total_boxes} total redaction boxes",
    "structuredContent": {
      "file_id": "string",
      "page_count": "number",
      "total_boxes": "number",
      "summary": "[per-page summary]"
    },
    "_meta": {
      "widgetAccessible": true,
      "phase": "detection_all",
      "pages": "[complete page data for widget]"
    }
  }
  ```

### 4. replace_redaction_boxes
- **Purpose**: Replace boxes of specific size with text
- **Annotations**:
  - readOnlyHint: false
  - destructiveHint: false (creates new file, doesn't modify original)
  - openWorldHint: true (custom replacement text)
- **Input Schema**:
  ```json
  {
    "file_id": "string (required) - File ID from upload_pdf",
    "box_width": "number (required) - Width in PDF points",
    "box_height": "number (required) - Height in PDF points",
    "replacement_text": "string (required) - Text to insert",
    "page_number": "number (optional) - Specific page or all pages",
    "size_tolerance": "number (optional, default: 2.0) - Tolerance in points"
  }
  ```
- **Output Structure**:
  ```json
  {
    "content": "Replaced {count} boxes with '{text}'. Download file ID: {modified_file_id}",
    "structuredContent": {
      "original_file_id": "string",
      "modified_file_id": "string",
      "total_boxes_replaced": "number",
      "pages_modified": "[array]"
    },
    "_meta": {
      "widgetAccessible": true,
      "phase": "replaced",
      "originalFileId": "string",
      "modifiedFileId": "string"
    }
  }
  ```
- **Widget Template**: `ui://widget/comparison.html`

### 5. download_pdf
- **Purpose**: Download processed PDF as base64
- **Annotations**:
  - readOnlyHint: true
  - destructiveHint: false
  - openWorldHint: false
- **Input Schema**:
  ```json
  {
    "file_id": "string (required) - File ID to download"
  }
  ```
- **Output Structure**:
  ```json
  {
    "content": "PDF ready for download ({size} bytes)",
    "structuredContent": {
      "file_id": "string",
      "size_bytes": "number"
    },
    "_meta": {
      "pdf_base64": "string - Full base64 content",
      "widgetAccessible": true
    }
  }
  ```

## Widget Design

### Widget Architecture
- **Type**: Multi-phase stateful widget
- **Framework**: React with TypeScript
- **Display Modes**:
  - Inline: Detection results card (compact)
  - Fullscreen: Side-by-side comparison viewer
  - PiP: Floating comparison (if needed)

### Widget Phases

| Phase | Trigger | Display | Actions |
|-------|---------|---------|---------|
| **upload** | Initial state | Drag-and-drop zone | Upload PDF |
| **detection** | After detect_black_boxes | Results card with box list | View details, select boxes |
| **comparison** | After replace_redaction_boxes | Side-by-side PDF viewer | Download, adjust view |

### Widget State
```typescript
interface WidgetState {
  phase: 'upload' | 'detection' | 'comparison';
  fileId?: string;
  modifiedFileId?: string;
  detectedBoxes?: Array<Box>;
  selectedBoxSize?: { width: number; height: number };
  currentPage?: number;
  replacementText?: string;
}
```

### UI Components Needed
1. **DropZone** - PDF drag-and-drop upload
2. **DetectionCard** - Inline results display with box grouping
3. **ComparisonView** - Fullscreen side-by-side PDF viewer
4. **BoxHighlight** - SVG overlay for detected boxes
5. **ActionBar** - Controls for replacement and download

### Design Tokens
- Use Apps SDK UI tokens (see apps_sdk_ui_tokens.md)
- Support dark mode via CSS variables
- Mobile-responsive (test at 375px width)

## Authentication
- **Required**: No
- **Reason**: Public API, no user-specific data or write operations to user accounts

## Server Requirements Checklist

### Endpoints to Add/Verify
- [ ] `/.well-known/openai-apps-challenge` - Challenge token endpoint
- [ ] `/privacy` - Privacy policy HTML
- [ ] `/terms` - Terms of service HTML
- [ ] `/mcp` - SSE MCP endpoint (already exists ✅)
- [ ] `/health` - Health check (already exists ✅)

### Security Headers
- [ ] CORS for ChatGPT domains only
- [ ] Rate limiting per session
- [ ] Input validation for all tools
- [ ] Safe HTML output (no XSS)

### Tool Metadata
- [ ] Add `_meta.openai/outputTemplate` to widget-enabled tools
- [ ] Add `_meta.openai/widgetAccessible` flag
- [ ] Include proper annotations on all tools

## Next Steps
1. ✅ Phase 1 Complete: Fit evaluation and golden prompts
2. 🔄 Phase 2 In Progress: Tool and widget specifications
3. ⏭️ Phase 3: Implement widget and add required server endpoints
4. ⏭️ Phase 4: Test with MCP Inspector and ChatGPT
5. ⏭️ Phase 5: Deploy and submit to App Store
