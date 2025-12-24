"""
Unredactor MCP - PDF Black Box Detection and Replacement

A Model Context Protocol (MCP) server that helps AI assistants detect
and replace black redaction boxes in PDF documents.
"""

__version__ = "0.1.0"

from .server import main

__all__ = ["main"]
