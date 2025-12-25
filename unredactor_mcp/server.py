"""
Unredactor - Remote MCP Server
A public MCP server that lets AI assistants detect and replace PDF redaction boxes.

Deploy to: Railway, Render, Fly.io, or any platform that supports Python web apps.
"""

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import base64
import tempfile
import os
import uuid
from typing import Any

from fastmcp import FastMCP

# Create the MCP server with HTTP transport
mcp = FastMCP(
    "unredactor",
    instructions="""
    Unredactor - PDF Black Box Detection and Replacement Tool

    This tool helps detect and replace black redaction boxes in PDF documents.

    Workflow:
    1. Upload a PDF using upload_pdf (provide base64-encoded content)
    2. Use detect_black_boxes to find redaction boxes
    3. Use replace_redaction_boxes to replace boxes of a specific size with text
    4. Download the modified PDF using download_pdf

    Note: Uploaded files are temporary and will be deleted after the session.
    """
)

# Temporary storage for uploaded PDFs (in production, use proper storage)
TEMP_DIR = tempfile.mkdtemp(prefix="unredactor_")
uploaded_files: dict[str, str] = {}


def find_boxes_in_pdf(pdf_path: str, page_num: int = 0) -> list[dict]:
    """Find all black rectangles on a PDF page using image processing."""
    doc = fitz.open(pdf_path)

    if page_num >= len(doc):
        doc.close()
        raise ValueError(f"Page {page_num} does not exist. PDF has {len(doc)} pages.")

    page = doc[page_num]
    boxes = []

    # Render page to image at 2x for better detection
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")

    # Convert to OpenCV format
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold to find black regions
    _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter for rectangular regions
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        # Filter out very small or very large boxes
        if w > 20 and h > 10 and w < pix.width * 0.8 and h < pix.height * 0.8:
            # Convert back to PDF coordinates (accounting for 2x scaling)
            pdf_x0 = x / 2
            pdf_y0 = y / 2
            pdf_x1 = (x + w) / 2
            pdf_y1 = (y + h) / 2

            boxes.append({
                "x0": round(pdf_x0, 1),
                "y0": round(pdf_y0, 1),
                "x1": round(pdf_x1, 1),
                "y1": round(pdf_y1, 1),
                "width": round((pdf_x1 - pdf_x0), 1),
                "height": round((pdf_y1 - pdf_y0), 1),
                "page": page_num
            })

    doc.close()
    return boxes


def is_pdf_text_based(pdf_path: str, sample_pages: int = 3) -> dict:
    """
    Determine if a PDF contains actual text or is image-based (scanned).

    Args:
        pdf_path: Path to the PDF file
        sample_pages: Number of pages to check (default: 3)

    Returns:
        Dictionary with analysis results
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    pages_to_check = min(sample_pages, total_pages)

    results = {
        "is_text_based": False,
        "total_pages": total_pages,
        "pages_checked": pages_to_check,
        "pages_with_text": 0,
        "pages_with_images": 0,
        "average_text_length": 0,
        "page_details": []
    }

    total_text_length = 0

    for page_num in range(pages_to_check):
        page = doc[page_num]

        # Extract text from the page
        text = page.get_text("text").strip()
        text_length = len(text)

        # Count images on the page
        image_list = page.get_images()
        image_count = len(image_list)

        # Determine if page has meaningful text (more than just headers/footers)
        has_text = text_length > 100  # Threshold for "meaningful" text
        has_images = image_count > 0

        page_info = {
            "page": page_num,
            "text_length": text_length,
            "image_count": image_count,
            "has_meaningful_text": has_text,
            "has_images": has_images
        }

        results["page_details"].append(page_info)
        total_text_length += text_length

        if has_text:
            results["pages_with_text"] += 1
        if has_images:
            results["pages_with_images"] += 1

    results["average_text_length"] = total_text_length / pages_to_check if pages_to_check > 0 else 0

    # Determine if PDF is text-based
    # If majority of sampled pages have meaningful text, consider it text-based
    results["is_text_based"] = results["pages_with_text"] > (pages_to_check / 2)

    # Add recommendation
    if results["is_text_based"]:
        results["recommendation"] = "PDF contains text - direct text extraction will work"
    else:
        results["recommendation"] = "PDF appears to be image-based - OCR may be required for text extraction"

    doc.close()
    return results


def extract_text_from_region(page, x0, y0, x1, y1, use_ocr=True):
    """
    Extract text from a specific region of a PDF page.

    First tries to extract text from the PDF text layer.
    If no text found and use_ocr=True, uses Tesseract OCR on the region.

    Args:
        page: PyMuPDF page object
        x0, y0, x1, y1: Coordinates of the region
        use_ocr: Whether to use OCR as fallback (default: True)

    Returns:
        Extracted text or "[No text found]"
    """
    import pytesseract

    # First try: Extract text from PDF text layer
    rect = fitz.Rect(x0, y0, x1, y1)
    text = page.get_text("text", clip=rect).strip()

    # If we found meaningful text, return it
    if text and len(text) > 2:  # At least 3 characters
        return text

    # Second try: Use OCR if enabled and no text found
    if use_ocr:
        try:
            # Render the region at high resolution for better OCR
            mat = fitz.Matrix(3, 3)  # 3x scale for OCR accuracy
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            # Run OCR
            ocr_text = pytesseract.image_to_string(img, config='--psm 6').strip()

            if ocr_text:
                return f"{ocr_text} [OCR]"  # Mark as OCR-extracted

        except Exception as e:
            print(f"OCR failed: {e}")

    return "[No text found]"


def replace_boxes_in_pdf(
    pdf_path: str,
    output_path: str,
    target_width: float,
    target_height: float,
    replacement_text: str,
    page_num: int | None = None,
    tolerance: float = 2.0
) -> dict:
    """Replace boxes of a specific size with white boxes containing text."""
    doc = fitz.open(pdf_path)
    total_replaced = 0
    pages_modified = []
    discovered_text = []  # Track text found under redaction boxes

    # Determine which pages to process
    if page_num is not None:
        if page_num >= len(doc):
            doc.close()
            raise ValueError(f"Page {page_num} does not exist. PDF has {len(doc)} pages.")
        page_range = [page_num]
    else:
        page_range = range(len(doc))

    for pnum in page_range:
        page = doc[pnum]

        # Find boxes on this page
        boxes = find_boxes_in_pdf(pdf_path, pnum)

        # Filter for matching dimensions
        matching_boxes = [
            box for box in boxes
            if abs(box["width"] - target_width) <= tolerance
            and abs(box["height"] - target_height) <= tolerance
        ]

        if not matching_boxes:
            continue

        # Render page to image at high resolution
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        draw = ImageDraw.Draw(img)

        count = 0
        for box in matching_boxes:
            # FIRST: Extract text from under the redaction box (before covering it)
            hidden_text = extract_text_from_region(page, box["x0"], box["y0"], box["x1"], box["y1"])
            discovered_text.append({
                "page": pnum,
                "box": f"({box['x0']:.1f}, {box['y0']:.1f}, {box['x1']:.1f}, {box['y1']:.1f})",
                "text": hidden_text,
                "size": f"{box['width']:.1f}x{box['height']:.1f}"
            })

            # Scale coordinates by 2 (since we rendered at 2x)
            x0 = box["x0"] * 2
            y0 = box["y0"] * 2
            x1 = box["x1"] * 2
            y1 = box["y1"] * 2

            # Draw white rectangle
            draw.rectangle([x0, y0, x1, y1], fill='white', outline='black', width=2)

            # Add text
            font_size = int(min(box["height"] * 0.6, 12) * 2)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()

            # Center the text
            bbox = draw.textbbox((0, 0), replacement_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = x0 + (x1 - x0 - text_width) / 2
            text_y = y0 + (y1 - y0 - text_height) / 2

            draw.text((text_x, text_y), replacement_text, fill='black', font=font)
            count += 1

        if count > 0:
            # Convert back to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Replace the page with the modified image
            img_pdf = fitz.open("png", img_bytes.read())
            pdf_bytes = img_pdf.convert_to_pdf()
            img_pdf.close()

            # Replace the page
            doc.delete_page(pnum)
            doc.insert_pdf(fitz.open("pdf", pdf_bytes), from_page=0, to_page=0, start_at=pnum)

            total_replaced += count
            pages_modified.append(pnum)

    # Save the modified PDF
    doc.save(output_path)
    doc.close()

    return {
        "total_boxes_replaced": total_replaced,
        "pages_modified": pages_modified,
        "output_path": output_path,
        "discovered_text": discovered_text,
        "unredacted_count": len([d for d in discovered_text if d["text"] != "[No text found]"])
    }


# ============== MCP Tools ==============

@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False})
def upload_pdf(pdf_base64: str, filename: str = "document.pdf") -> dict:
    """
    Upload a PDF file for processing.

    The PDF content should be base64-encoded. Returns a file_id that you'll
    use with other tools.

    IMPORTANT: For large PDFs (>10MB), consider:
    - Splitting into smaller files (5-10 pages each)
    - Using the HTTP API endpoint /api/call-tool instead
    - Ensuring base64 is complete with no truncation

    Args:
        pdf_base64: Base64-encoded PDF file content (must be complete, no truncation)
        filename: Optional filename for reference

    Returns:
        Dictionary with file_id to use in subsequent operations
    """
    # Check for common issues
    if pdf_base64.startswith("{{FILE_BASE64:") or "{{" in pdf_base64:
        raise ValueError(
            "Received a placeholder instead of actual base64 data. "
            "Please encode the PDF file to base64 first. "
            "For large files, consider using the HTTP API endpoint directly."
        )

    if len(pdf_base64) < 100:
        raise ValueError(
            f"Base64 string too short ({len(pdf_base64)} chars). "
            "Please provide the complete base64-encoded PDF content."
        )

    # Warn about large files
    estimated_size_mb = len(pdf_base64) * 0.75 / (1024 * 1024)  # base64 is ~133% of original
    if estimated_size_mb > 10:
        # Still allow it, but warn
        print(f"Warning: Large PDF ({estimated_size_mb:.1f} MB). This may cause issues.")

    try:
        pdf_bytes = base64.b64decode(pdf_base64)
    except Exception as e:
        error_msg = str(e)
        if "Incorrect padding" in error_msg:
            raise ValueError(
                f"Invalid base64 content: {error_msg}. "
                "The base64 string appears to be truncated or incomplete. "
                "Ensure you're sending the COMPLETE base64-encoded file with no truncation."
            )
        raise ValueError(f"Invalid base64 content: {e}")

    # Validate it's a PDF
    if not pdf_bytes.startswith(b'%PDF'):
        raise ValueError("Invalid PDF file - content does not start with PDF header")

    # Generate unique ID and save
    file_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(TEMP_DIR, f"{file_id}.pdf")

    with open(file_path, 'wb') as f:
        f.write(pdf_bytes)

    uploaded_files[file_id] = file_path

    # Get basic info
    doc = fitz.open(file_path)
    page_count = len(doc)
    doc.close()

    return {
        "file_id": file_id,
        "filename": filename,
        "page_count": page_count,
        "message": f"PDF uploaded successfully. Use file_id '{file_id}' for subsequent operations.",
        "_meta": {
            "widgetAccessible": True,
            "phase": "uploaded"
        }
    }


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})
def get_pdf_info(file_id: str) -> dict:
    """
    Get information about an uploaded PDF file.

    Args:
        file_id: The file ID returned from upload_pdf

    Returns:
        Dictionary with PDF metadata including page count and page dimensions
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found. Please upload a PDF first.")

    pdf_path = uploaded_files[file_id]
    doc = fitz.open(pdf_path)

    info = {
        "file_id": file_id,
        "page_count": len(doc),
        "pages": []
    }

    for i, page in enumerate(doc):
        rect = page.rect
        info["pages"].append({
            "page_number": i,
            "width": round(rect.width, 1),
            "height": round(rect.height, 1)
        })

    doc.close()
    return info


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})
def analyze_pdf_type(file_id: str, sample_pages: int = 3) -> dict:
    """
    Analyze whether a PDF contains actual text or is image-based (scanned).

    This is useful to determine if text extraction will work or if OCR is needed.

    Args:
        file_id: The file ID returned from upload_pdf
        sample_pages: Number of pages to analyze (default: 3)

    Returns:
        Dictionary with analysis results including whether PDF is text-based
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found. Please upload a PDF first.")

    pdf_path = uploaded_files[file_id]
    return is_pdf_text_based(pdf_path, sample_pages)


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})
def detect_boxes_direct(pdf_base64: str, page_number: int = 0) -> dict:
    """
    Detect black boxes directly from base64 PDF data without upload.

    This is useful for quick analysis or when upload_pdf fails with large files.
    Processes the PDF in memory without saving to disk.

    Args:
        pdf_base64: Base64-encoded PDF file content
        page_number: Page number to analyze (0-indexed, default 0)

    Returns:
        Dictionary with detected boxes and analysis
    """
    import tempfile

    # Decode PDF
    try:
        pdf_bytes = base64.b64decode(pdf_base64)
    except Exception as e:
        raise ValueError(f"Invalid base64 content: {e}")

    if not pdf_bytes.startswith(b'%PDF'):
        raise ValueError("Invalid PDF file")

    # Save to temp file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        boxes = find_boxes_in_pdf(tmp_path, page_number)
        pdf_analysis = is_pdf_text_based(tmp_path, sample_pages=1)

        return {
            "page_number": page_number,
            "total_boxes_found": len(boxes),
            "boxes": boxes,
            "pdf_type": pdf_analysis["recommendation"],
            "message": f"Found {len(boxes)} boxes on page {page_number}"
        }
    finally:
        os.unlink(tmp_path)


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})
def detect_black_boxes(file_id: str, page_number: int = 0) -> dict:
    """
    Detect black boxes (redactions) on a PDF page.

    This uses image processing to find black rectangular regions that
    may be redaction boxes.

    Args:
        file_id: The file ID returned from upload_pdf
        page_number: Page number to analyze (0-indexed, default 0)

    Returns:
        Dictionary with list of detected boxes and their dimensions
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found. Please upload a PDF first.")

    pdf_path = uploaded_files[file_id]
    boxes = find_boxes_in_pdf(pdf_path, page_number)

    # Analyze if PDF is text-based or image-based
    pdf_analysis = is_pdf_text_based(pdf_path, sample_pages=1)

    # Group boxes by size for easier selection
    size_groups = {}
    for box in boxes:
        size_key = f"{box['width']}x{box['height']}"
        if size_key not in size_groups:
            size_groups[size_key] = {
                "width": box["width"],
                "height": box["height"],
                "count": 0,
                "boxes": []
            }
        size_groups[size_key]["count"] += 1
        size_groups[size_key]["boxes"].append({
            "x0": box["x0"],
            "y0": box["y0"],
            "x1": box["x1"],
            "y1": box["y1"]
        })

    return {
        "file_id": file_id,
        "page_number": page_number,
        "total_boxes_found": len(boxes),
        "boxes_by_size": list(size_groups.values()),
        "boxes": boxes,
        "pdf_type": {
            "is_text_based": pdf_analysis["is_text_based"],
            "recommendation": pdf_analysis["recommendation"],
            "average_text_length": pdf_analysis["average_text_length"]
        },
        "_meta": {
            "widgetAccessible": True,
            "phase": "detection",
            "all_boxes": boxes,
            "pdf_analysis": pdf_analysis
        }
    }


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})
def detect_all_pages(file_id: str) -> dict:
    """
    Detect black boxes on all pages of a PDF.

    Args:
        file_id: The file ID returned from upload_pdf

    Returns:
        Dictionary with detected boxes for each page
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found. Please upload a PDF first.")

    pdf_path = uploaded_files[file_id]
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    doc.close()

    results = {
        "file_id": file_id,
        "page_count": page_count,
        "pages": []
    }

    total_boxes = 0
    for page_num in range(page_count):
        boxes = find_boxes_in_pdf(pdf_path, page_num)
        total_boxes += len(boxes)
        results["pages"].append({
            "page_number": page_num,
            "boxes_found": len(boxes),
            "boxes": boxes
        })

    results["total_boxes"] = total_boxes
    results["_meta"] = {
        "widgetAccessible": True,
        "phase": "detection_all",
        "pages": results["pages"]
    }
    return results


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
def replace_redaction_boxes(
    file_id: str,
    box_width: float,
    box_height: float,
    replacement_text: str,
    page_number: int | None = None,
    size_tolerance: float = 2.0
) -> dict:
    """
    Replace black boxes of a specific size with white boxes containing text.

    First use detect_black_boxes to find boxes and their dimensions, then
    use this tool to replace boxes of a specific size.

    Args:
        file_id: The file ID returned from upload_pdf
        box_width: Width of boxes to replace (in PDF points)
        box_height: Height of boxes to replace (in PDF points)
        replacement_text: Text to place inside the replacement white boxes
        page_number: Specific page to modify (0-indexed), or None for all pages
        size_tolerance: How much variation in size to allow (default 2.0 points)

    Returns:
        Dictionary with information about the replacement operation
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found. Please upload a PDF first.")

    pdf_path = uploaded_files[file_id]

    # Create output path
    output_id = str(uuid.uuid4())[:8]
    output_path = os.path.join(TEMP_DIR, f"{output_id}_modified.pdf")

    result = replace_boxes_in_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        target_width=box_width,
        target_height=box_height,
        replacement_text=replacement_text,
        page_num=page_number,
        tolerance=size_tolerance
    )

    # Register the output file
    uploaded_files[output_id] = output_path

    return {
        "original_file_id": file_id,
        "modified_file_id": output_id,
        "processed_file_id": output_id,
        "total_boxes_replaced": result["total_boxes_replaced"],
        "replaced_count": result["total_boxes_replaced"],
        "pages_modified": result["pages_modified"],
        "discovered_text": result.get("discovered_text", []),
        "unredacted_count": result.get("unredacted_count", 0),
        "message": f"Replaced {result['total_boxes_replaced']} boxes. Found text under {result.get('unredacted_count', 0)} of them. Use download_pdf with file_id '{output_id}' to get the modified PDF.",
        "_meta": {
            "widgetAccessible": True,
            "phase": "replaced",
            "originalFileId": file_id,
            "modifiedFileId": output_id,
            "discoveredText": result.get("discovered_text", [])
        }
    }


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})
def download_pdf(file_id: str) -> dict:
    """
    Download a PDF file as base64-encoded content.

    Use this to retrieve the modified PDF after using replace_redaction_boxes.

    Args:
        file_id: The file ID of the PDF to download

    Returns:
        Dictionary with base64-encoded PDF content
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found.")

    pdf_path = uploaded_files[file_id]

    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    return {
        "file_id": file_id,
        "pdf_base64": base64.b64encode(pdf_bytes).decode('utf-8'),
        "size_bytes": len(pdf_bytes),
        "_meta": {
            "pdf_base64": base64.b64encode(pdf_bytes).decode('utf-8'),
            "widgetAccessible": True
        }
    }


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False})
def cleanup_file(file_id: str) -> dict:
    """
    Delete an uploaded file to free up space.

    Args:
        file_id: The file ID to delete

    Returns:
        Confirmation of deletion
    """
    if file_id not in uploaded_files:
        raise ValueError(f"File ID '{file_id}' not found.")

    pdf_path = uploaded_files[file_id]

    try:
        os.remove(pdf_path)
    except:
        pass

    del uploaded_files[file_id]

    return {
        "file_id": file_id,
        "message": "File deleted successfully"
    }


# Add required ChatGPT App endpoints
from starlette.responses import JSONResponse, PlainTextResponse, HTMLResponse, FileResponse, RedirectResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
import os

async def health_check(request):
    """Simple health check endpoint for Railway."""
    return JSONResponse({"status": "healthy", "service": "unredactor-mcp"})

async def well_known_challenge(request):
    """OpenAI Apps Challenge endpoint for domain verification."""
    # TODO: Replace with actual challenge token from OpenAI Platform
    return PlainTextResponse("CHALLENGE_TOKEN_PLACEHOLDER")

async def privacy_policy(request):
    """Privacy policy page."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy - Unredactor</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }
        h1 { color: #1a1a1a; }
        h2 { color: #333; margin-top: 30px; }
        p { margin-bottom: 15px; }
        .contact { background: #f5f5f5; padding: 15px; border-radius: 8px; margin-top: 30px; }
    </style>
</head>
<body>
    <h1>Privacy Policy</h1>
    <p><strong>Effective Date:</strong> December 2024</p>

    <h2>Information We Collect</h2>
    <p>Unredactor processes PDF files temporarily to detect and replace redaction boxes. We collect:</p>
    <ul>
        <li>Uploaded PDF files (stored temporarily)</li>
        <li>Basic usage metrics (request counts, error rates)</li>
    </ul>

    <h2>How We Use Information</h2>
    <p>We use collected information solely to:</p>
    <ul>
        <li>Process your PDF files for redaction detection</li>
        <li>Improve service reliability and performance</li>
        <li>Debug technical issues</li>
    </ul>

    <h2>Data Storage and Retention</h2>
    <p>Uploaded PDF files are stored temporarily in memory during processing and are automatically deleted after the session ends. We do not permanently store user files.</p>

    <h2>Third-Party Services</h2>
    <p>We use Railway for hosting infrastructure. No user data is shared with third parties for marketing or advertising purposes.</p>

    <h2>Data Sharing</h2>
    <p>We do not sell, trade, or share your data with third parties, except as required by law.</p>

    <h2>User Rights</h2>
    <p>You have the right to:</p>
    <ul>
        <li>Request deletion of your data</li>
        <li>Access information we have collected</li>
        <li>Opt out of data collection (by not using the service)</li>
    </ul>

    <div class="contact">
        <h2>Contact Information</h2>
        <p>For privacy concerns or questions, please contact us at: privacy@unredactor.com</p>
    </div>
</body>
</html>"""
    return HTMLResponse(html)

async def terms_of_service(request):
    """Terms of service page."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms of Service - Unredactor</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }
        h1 { color: #1a1a1a; }
        h2 { color: #333; margin-top: 30px; }
        p { margin-bottom: 15px; }
        .contact { background: #f5f5f5; padding: 15px; border-radius: 8px; margin-top: 30px; }
    </style>
</head>
<body>
    <h1>Terms of Service</h1>
    <p><strong>Effective Date:</strong> December 2024</p>

    <h2>Service Description</h2>
    <p>Unredactor is a tool that detects and replaces black redaction boxes in PDF documents. The service is provided "as is" without warranties.</p>

    <h2>Acceptable Use Policy</h2>
    <p>You agree to use Unredactor only for lawful purposes. Prohibited activities include:</p>
    <ul>
        <li>Processing documents you don't have legal rights to modify</li>
        <li>Attempting to circumvent security measures</li>
        <li>Uploading malicious files or malware</li>
        <li>Excessive automated usage that impacts service availability</li>
    </ul>

    <h2>Data and Privacy</h2>
    <p>Your use of the service is governed by our <a href="/privacy">Privacy Policy</a>. By using Unredactor, you agree to our data practices.</p>

    <h2>Intellectual Property</h2>
    <p>You retain all rights to your uploaded PDF files. We do not claim ownership of user content.</p>

    <h2>Disclaimers and Limitation of Liability</h2>
    <p>Unredactor is provided "as is" without warranties. We are not liable for any damages arising from use of the service, including but not limited to data loss or incorrect redaction detection.</p>

    <h2>Rate Limits and Usage Restrictions</h2>
    <p>We may implement rate limiting to ensure fair usage. Excessive usage may result in temporary service restrictions.</p>

    <h2>Modifications and Termination</h2>
    <p>We reserve the right to modify or terminate the service at any time. We will provide notice of material changes when possible.</p>

    <h2>Governing Law</h2>
    <p>These terms are governed by the laws of the jurisdiction where the service is operated.</p>

    <div class="contact">
        <h2>Contact Information</h2>
        <p>For questions about these terms, contact us at: support@unredactor.com</p>
    </div>
</body>
</html>"""
    return HTMLResponse(html)

async def serve_widget_html(request):
    """Serve the widget HTML file."""
    widget_path = os.path.join(os.path.dirname(__file__), "static/widget.html")
    if os.path.exists(widget_path):
        return FileResponse(widget_path, media_type="text/html")
    return HTMLResponse("<html><body><h1>Widget not found</h1></body></html>", status_code=404)

async def serve_widget_js(request):
    """Serve the widget JavaScript bundle."""
    widget_path = os.path.join(os.path.dirname(__file__), "static/widget.js")
    if os.path.exists(widget_path):
        return FileResponse(widget_path, media_type="application/javascript")
    return PlainTextResponse("// Widget JS not found", status_code=404)

async def serve_widget_css(request):
    """Serve the widget CSS file."""
    widget_path = os.path.join(os.path.dirname(__file__), "static/widget.css")
    if os.path.exists(widget_path):
        return FileResponse(widget_path, media_type="text/css")
    return PlainTextResponse("/* Widget CSS not found */", status_code=404)

async def serve_root(request):
    """Redirect root to widget."""
    return RedirectResponse(url="/widget.html")

async def serve_demo_pdf(request):
    """Serve the demo PDF file."""
    demo_pdf_path = os.path.join(os.path.dirname(__file__), "../epstein-documents/TEST_REDACTED.pdf")
    if os.path.exists(demo_pdf_path):
        return FileResponse(demo_pdf_path, media_type="application/pdf", filename="demo.pdf")
    return JSONResponse({'error': 'Demo PDF not found'}, status_code=404)

async def call_tool_http(request):
    """HTTP endpoint for standalone widget testing - wraps MCP tool calls."""
    try:
        body = await request.json()
        tool_name = body.get('tool')
        args = body.get('args', {})

        # Call the appropriate tool function
        if tool_name == 'detect_black_boxes':
            # Decode base64 PDF data and save to temp file
            import base64
            import tempfile
            pdf_data = base64.b64decode(args.get('pdf_data'))
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name

            try:
                boxes = find_boxes_in_pdf(tmp_path, args.get('page_number', 0))
                result = {'boxes': boxes, 'page_number': args.get('page_number', 0)}
            finally:
                os.unlink(tmp_path)

        elif tool_name == 'replace_redaction_boxes':
            # Decode base64 PDF data and save to temp file
            import base64
            import tempfile
            pdf_data = base64.b64decode(args.get('pdf_data'))
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name

            output_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            output_path = output_tmp.name
            output_tmp.close()

            try:
                replacement_result = replace_boxes_in_pdf(
                    pdf_path=tmp_path,
                    output_path=output_path,
                    target_width=args.get('box_width'),
                    target_height=args.get('box_height'),
                    replacement_text=args.get('replacement_text'),
                    page_num=args.get('page_number', 0),
                    tolerance=args.get('size_tolerance', 2.0)
                )

                # Read output file and encode as base64
                with open(output_path, 'rb') as f:
                    output_data = base64.b64encode(f.read()).decode()

                # Also return the original PDF for side-by-side comparison
                result = {
                    'processed_pdf': output_data,
                    'original_pdf': args.get('pdf_data'),  # Pass through the original
                    'total_boxes_replaced': replacement_result.get('total_boxes_replaced', 0),
                    'discovered_text': replacement_result.get('discovered_text', []),
                    'pages_modified': replacement_result.get('pages_modified', []),
                    'unredacted_count': replacement_result.get('unredacted_count', 0)
                }
            finally:
                os.unlink(tmp_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
        else:
            return JSONResponse({'error': f'Unknown tool: {tool_name}'}, status_code=400)

        return JSONResponse(result)
    except Exception as e:
        print(f"Tool call error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({'error': str(e)}, status_code=500)

# Create the base MCP app (it has /mcp route internally)
mcp_app = mcp.http_app()

# Create a wrapper Starlette app with all routes
# Note: FastMCP's http_app already has a /mcp route, so we mount at root
# This way the internal /mcp route becomes accessible at /mcp (not /mcp/mcp)
routes = [
    Route("/", serve_root),
    Route("/health", health_check),
    Route("/api/call-tool", call_tool_http, methods=["POST"]),  # Standalone widget endpoint
    Route("/api/demo-pdf", serve_demo_pdf),  # Demo PDF endpoint
    Route("/.well-known/openai-apps-challenge", well_known_challenge),
    Route("/privacy", privacy_policy),
    Route("/terms", terms_of_service),
    Route("/widget.html", serve_widget_html),
    Route("/widget.js", serve_widget_js),
    Route("/widget.css", serve_widget_css),
]

# Create main app with MCP's lifespan and mount MCP app at root so /mcp is accessible
app = Starlette(routes=routes, lifespan=mcp_app.lifespan)
app.mount("/", mcp_app)

# Add CORS middleware for local testing with MCP Inspector
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def main():
    """Entry point for the MCP server."""
    import uvicorn
    import sys

    print("=" * 50, flush=True)
    print("Unredactor MCP Server Starting", flush=True)
    print(f"Python version: {sys.version}", flush=True)
    print(f"PORT env var: {os.environ.get('PORT', 'NOT SET')}", flush=True)

    port = int(os.environ.get("PORT", 8080))
    print(f"Using port: {port}", flush=True)
    print(f"App: {app}", flush=True)
    print("=" * 50, flush=True)

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


# Run the server
if __name__ == "__main__":
    main()
