"""
Unredactor MCP Server
Exposes PDF black box detection and replacement as MCP tools.

To run:
    python unredactor_mcp.py

Or add to Claude Code's MCP config.
"""

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import base64
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("unredactor")


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
        "output_path": output_path
    }


# ============== MCP Tools ==============

@mcp.tool()
def get_pdf_info(pdf_path: str) -> dict:
    """
    Get information about a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with PDF metadata including page count and page dimensions
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    info = {
        "path": pdf_path,
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


@mcp.tool()
def detect_black_boxes(pdf_path: str, page_number: int = 0) -> dict:
    """
    Detect black boxes (redactions) on a PDF page.

    This uses image processing to find black rectangular regions that
    may be redaction boxes.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number to analyze (0-indexed, default 0)

    Returns:
        Dictionary with list of detected boxes and their dimensions
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    boxes = find_boxes_in_pdf(pdf_path, page_number)

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
        "pdf_path": pdf_path,
        "page_number": page_number,
        "total_boxes_found": len(boxes),
        "boxes_by_size": list(size_groups.values()),
        "all_boxes": boxes
    }


@mcp.tool()
def replace_redaction_boxes(
    pdf_path: str,
    output_path: str,
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
        pdf_path: Path to the input PDF file
        output_path: Path where the modified PDF will be saved
        box_width: Width of boxes to replace (in PDF points)
        box_height: Height of boxes to replace (in PDF points)
        replacement_text: Text to place inside the replacement white boxes
        page_number: Specific page to modify (0-indexed), or None for all pages
        size_tolerance: How much variation in size to allow (default 2.0 points)

    Returns:
        Dictionary with information about the replacement operation
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    result = replace_boxes_in_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        target_width=box_width,
        target_height=box_height,
        replacement_text=replacement_text,
        page_num=page_number,
        tolerance=size_tolerance
    )

    return result


@mcp.tool()
def detect_all_pages(pdf_path: str) -> dict:
    """
    Detect black boxes on all pages of a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with detected boxes for each page
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    doc.close()

    results = {
        "pdf_path": pdf_path,
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
    return results


# Run the server
if __name__ == "__main__":
    mcp.run()
