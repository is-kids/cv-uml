"""Pydantic models for CV-UML."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class FileType(str, Enum):
    """Supported file types."""

    IMAGE = "image"  # PNG, JPG, JPEG, BMP, GIF, WEBP
    SVG = "svg"
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"
    DRAWIO = "drawio"
    BPMN = "bpmn"
    ARCHIVE = "archive"  # ZIP, RAR, 7Z
    UNKNOWN = "unknown"


class DiagramStep(BaseModel):
    """A single step in a diagram."""

    number: int = Field(..., description="Step number (1-indexed)")
    actor: Optional[str] = Field(None, description="Actor performing the step")
    action: str = Field(..., description="Action description")
    target: Optional[str] = Field(None, description="Target of the action")
    note: Optional[str] = Field(None, description="Additional notes")


class ExtractionResult(BaseModel):
    """Result of extracting steps from a single file/image."""

    source_file: str = Field(..., description="Original source file path")
    page_or_slide: Optional[int] = Field(
        None, description="Page/slide number if from multi-page document"
    )
    diagram_type: Optional[str] = Field(
        None, description="Detected diagram type (sequence, flowchart, etc.)"
    )
    steps: list[DiagramStep] = Field(default_factory=list, description="Extracted steps")
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score of extraction"
    )
    error: Optional[str] = Field(None, description="Error message if extraction failed")


class FileInput(BaseModel):
    """Input file metadata."""

    path: Path = Field(..., description="File path")
    file_type: FileType = Field(..., description="Detected file type")
    parent_archive: Optional[str] = Field(
        None, description="Parent archive path if extracted from archive"
    )


class BatchResult(BaseModel):
    """Result of batch processing."""

    total_files: int = Field(..., description="Total files processed")
    successful: int = Field(..., description="Successfully processed files")
    failed: int = Field(..., description="Failed files")
    results: list[ExtractionResult] = Field(
        default_factory=list, description="All extraction results"
    )


class GenerateRequest(BaseModel):
    """Request to generate PlantUML diagram from steps."""

    steps: list[DiagramStep] = Field(..., description="Steps to convert to diagram")
    diagram_type: str = Field(
        "sequence", description="Type of diagram to generate (sequence, activity)"
    )
    title: Optional[str] = Field(None, description="Diagram title")


class GenerateResponse(BaseModel):
    """Response with generated diagram."""

    plantuml_code: str = Field(..., description="Generated PlantUML code")
    png_base64: Optional[str] = Field(None, description="PNG image as base64 string")
    error: Optional[str] = Field(None, description="Error message if generation failed")
