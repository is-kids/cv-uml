"""Post-processing utilities for LLM output parsing."""

import json
import logging
import re
from typing import Optional

from app.models import DiagramStep, ExtractionResult

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON object from text that may contain other content.

    Args:
        text: Text potentially containing JSON

    Returns:
        Extracted JSON string or None
    """
    # Try to find JSON object
    # Look for { ... } pattern
    brace_count = 0
    start_idx = None
    end_idx = None

    for i, char in enumerate(text):
        if char == "{":
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_idx is not None:
                end_idx = i + 1
                break

    if start_idx is not None and end_idx is not None:
        return text[start_idx:end_idx]

    return None


def parse_json_response(text: str) -> Optional[dict]:
    """
    Parse JSON from LLM response.

    Args:
        text: LLM response text

    Returns:
        Parsed dictionary or None
    """
    # First try direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from text
    json_str = extract_json_from_text(text)
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Try fixing common issues
    # Remove trailing commas
    fixed = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    json_str = extract_json_from_text(fixed)
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse JSON from response")
    return None


def parse_simple_format(text: str) -> list[DiagramStep]:
    """
    Parse simple line-by-line step format as fallback.

    Expected format:
    1. Actor -> action -> Target
    or
    1. action description

    Args:
        text: Text with numbered steps

    Returns:
        List of DiagramStep objects
    """
    steps = []

    # Pattern for: number. actor -> action -> target
    arrow_pattern = r"(\d+)\.\s*([^->]+?)\s*->\s*(.+?)\s*->\s*([^->]+?)(?:\n|$)"

    # Pattern for: number. action description
    simple_pattern = r"(\d+)\.\s*(.+?)(?:\n|$)"

    # Try arrow pattern first
    arrow_matches = re.findall(arrow_pattern, text)
    if arrow_matches:
        for match in arrow_matches:
            num, actor, action, target = match
            actor = actor.strip() if actor.strip() != "?" else None
            target = target.strip() if target.strip() != "?" else None
            steps.append(
                DiagramStep(
                    number=int(num),
                    actor=actor,
                    action=action.strip(),
                    target=target,
                )
            )
        return steps

    # Fall back to simple pattern
    simple_matches = re.findall(simple_pattern, text)
    for match in simple_matches:
        num, action = match
        steps.append(
            DiagramStep(
                number=int(num),
                action=action.strip(),
            )
        )

    return steps


def parse_llm_response(
    text: str,
    source_file: str,
    page_or_slide: Optional[int] = None,
) -> ExtractionResult:
    """
    Parse LLM response into ExtractionResult.

    Args:
        text: LLM response text
        source_file: Source file path
        page_or_slide: Page or slide number

    Returns:
        ExtractionResult object
    """
    # Try JSON parsing first
    data = parse_json_response(text)

    if data and isinstance(data, dict):
        steps = []
        for i, step_data in enumerate(data.get("steps", [])):
            if isinstance(step_data, dict):
                steps.append(
                    DiagramStep(
                        number=step_data.get("number", i + 1),
                        actor=step_data.get("actor"),
                        action=step_data.get("action", "Unknown"),
                        target=step_data.get("target"),
                        note=step_data.get("note"),
                    )
                )

        return ExtractionResult(
            source_file=source_file,
            page_or_slide=page_or_slide,
            diagram_type=data.get("diagram_type"),
            steps=steps,
            confidence=float(data.get("confidence", 0.8)),
        )

    # Fall back to simple format parsing
    logger.info("Falling back to simple format parsing")
    steps = parse_simple_format(text)

    if steps:
        return ExtractionResult(
            source_file=source_file,
            page_or_slide=page_or_slide,
            steps=steps,
            confidence=0.5,  # Lower confidence for regex parsing
        )

    # No steps found
    return ExtractionResult(
        source_file=source_file,
        page_or_slide=page_or_slide,
        steps=[],
        confidence=0.0,
        error="Failed to parse any steps from LLM response",
    )


def validate_steps(steps: list[DiagramStep]) -> list[DiagramStep]:
    """
    Validate and clean up extracted steps.

    Args:
        steps: List of steps to validate

    Returns:
        Validated list of steps
    """
    valid_steps = []

    for step in steps:
        # Skip empty actions
        if not step.action or not step.action.strip():
            continue

        # Clean up action text
        action = step.action.strip()
        action = re.sub(r"\s+", " ", action)  # Normalize whitespace

        valid_steps.append(
            DiagramStep(
                number=step.number,
                actor=step.actor.strip() if step.actor else None,
                action=action,
                target=step.target.strip() if step.target else None,
                note=step.note.strip() if step.note else None,
            )
        )

    # Re-number steps
    for i, step in enumerate(valid_steps):
        step.number = i + 1

    return valid_steps


def merge_results(results: list[ExtractionResult]) -> ExtractionResult:
    """
    Merge multiple extraction results into one.

    Args:
        results: List of results to merge

    Returns:
        Merged ExtractionResult
    """
    if not results:
        return ExtractionResult(
            source_file="",
            steps=[],
            error="No results to merge",
        )

    if len(results) == 1:
        return results[0]

    # Combine all steps
    all_steps = []
    for result in results:
        all_steps.extend(result.steps)

    # Re-number
    for i, step in enumerate(all_steps):
        step.number = i + 1

    # Use first result's metadata
    first = results[0]

    return ExtractionResult(
        source_file=first.source_file,
        diagram_type=first.diagram_type,
        steps=all_steps,
        confidence=sum(r.confidence for r in results) / len(results),
    )
