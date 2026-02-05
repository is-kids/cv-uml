import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

from rich.console import Console
from rich.table import Table

console = Console()

# Test files for supported formats (use forward slashes for cross-platform)
TEST_FILES = {
    "PNG": "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture/1.png",
    "JPG": "docs/Диаграммы/Диаграммы/Телеграм_Диаграммы 2/uml/class.jpg",
    "DrawIO": "docs/Диаграммы/Диаграммы/Notion_Диаграммы/BPMN/bpmn.drawio",
    "BPMN": "docs/Диаграммы/Диаграммы/БиблиотечныйСервис_Диаграммы/BPMN/Process_Booking.bpmn",
}


def test_format(format_name: str, file_path: str) -> dict:
    """Test a single format."""
    from app.pipeline import process_path

    path = Path(file_path)
    if not path.exists():
        return {"status": "NOT_FOUND", "steps": 0, "time": 0, "error": "File not found", "results": []}

    try:
        start = time.time()
        results = process_path(path)
        elapsed = time.time() - start

        if not results:
            return {"status": "NO_RESULTS", "steps": 0, "time": elapsed, "error": "No results", "results": []}

        total_steps = sum(len(r.steps) for r in results if r.steps)
        errors = [r.error for r in results if r.error]

        if errors:
            return {"status": "ERROR", "steps": total_steps, "time": elapsed, "error": errors[0][:40], "results": results}

        return {"status": "OK", "steps": total_steps, "time": elapsed, "error": None, "results": results}

    except Exception as e:
        return {"status": "EXCEPTION", "steps": 0, "time": 0, "error": str(e)[:40], "results": []}


def main():
    console.print("\n[bold cyan]CV-UML Format Test[/bold cyan]\n")

    # Warmup
    console.print("[dim]Loading model...[/dim]")
    from app.llm import warmup, MODEL_ID, USE_4BIT
    console.print(f"[dim]Model: {MODEL_ID}, 4-bit: {USE_4BIT}[/dim]")

    start = time.time()
    warmup()
    load_time = time.time() - start
    console.print(f"[green]Model ready in {load_time:.1f}s[/green]\n")

    # Test each format
    table = Table(title="Format Test Results")
    table.add_column("Format", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Steps", justify="right")
    table.add_column("Time", justify="right")
    table.add_column("Error", style="dim")

    total_time = 0
    all_results = {}

    for format_name, file_path in TEST_FILES.items():
        console.print(f"[dim]Testing {format_name}...[/dim]")
        result = test_format(format_name, file_path)
        total_time += result["time"]
        all_results[format_name] = result

        status_color = "green" if result["status"] == "OK" else "yellow" if result["status"] == "NOT_FOUND" else "red"
        time_str = f"{result['time']:.1f}s" if result["time"] > 0 else "-"

        table.add_row(
            format_name,
            f"[{status_color}]{result['status']}[/{status_color}]",
            str(result["steps"]),
            time_str,
            result["error"] or ""
        )

    console.print(table)
    console.print(f"\n[bold]Total inference time: {total_time:.1f}s[/bold]")
    console.print(f"[bold]Average per file: {total_time/len(TEST_FILES):.1f}s[/bold]\n")

    # Show extracted steps for each format
    console.print("[bold cyan]Extracted Results:[/bold cyan]\n")

    for format_name, result in all_results.items():
        if not result["results"]:
            continue

        for r in result["results"]:
            console.print(f"[bold yellow]{format_name}[/bold yellow] - {r.source_file}")
            if r.diagram_type:
                console.print(f"  Type: {r.diagram_type}")

            if r.steps:
                for step in r.steps:
                    num = step.number or "•"
                    actor = f"[{step.actor}] " if step.actor else ""
                    target = f" -> {step.target}" if step.target else ""
                    console.print(f"  {num}. {actor}{step.action}{target}")
            else:
                console.print("  [dim]No steps extracted[/dim]")
            console.print()


if __name__ == "__main__":
    main()
