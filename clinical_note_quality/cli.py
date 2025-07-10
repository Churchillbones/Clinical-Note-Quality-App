"""Command-line interface for Clinical Note Quality grading.

Provides commands for grading single files, directories, or stdin input
with various output formats and precision settings.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    typer = None
    Console = None
    Progress = SpinnerColumn = TextColumn = None

from clinical_note_quality.services.grading_service import GradingService
from clinical_note_quality.domain import HybridResult


app = typer.Typer(name="clinical-note-quality", help="Clinical Note Quality Assessment Tool")
console = Console() if Console else None


class ClinicalNoteGrader:
    """High-level SDK class for clinical note grading."""
    
    def __init__(self) -> None:
        self.grading_service = GradingService()
    
    def grade(
        self, 
        note: str, 
        transcript: str = "", 
        precision: str = "medium"
    ) -> HybridResult:
        """Grade a clinical note and return detailed results."""
        return self.grading_service.grade(note, transcript, precision)
    
    async def grade_async(
        self, 
        note: str, 
        transcript: str = "", 
        precision: str = "medium"
    ) -> HybridResult:
        """Grade a clinical note asynchronously."""
        return await self.grading_service.grade_async(note, transcript, precision)


def _format_output(result: HybridResult, output_format: str) -> str:
    """Format grading result according to specified format."""
    if output_format == "json":
        return json.dumps(result.as_dict(), indent=2)
    elif output_format == "html":
        # Simple HTML output
        return f"""
<!DOCTYPE html>
<html>
<head><title>Clinical Note Quality Report</title></head>
<body>
    <h1>Clinical Note Quality Assessment</h1>
    <h2>Overall Grade: {result.overall_grade} (Score: {result.hybrid_score})</h2>
    
    <h3>PDQI Analysis</h3>
    <p>Average: {result.pdqi.average:.2f}</p>
    <p>Model: {result.pdqi.model_provenance}</p>
    <p>Summary: {result.pdqi.summary}</p>
    
    <h3>Heuristic Analysis</h3>
    <p>Composite Score: {result.heuristic.composite_score:.2f}</p>
    <p>Word Count: {result.heuristic.word_count}</p>
    
    <h3>Factuality Analysis</h3>
    <p>Consistency Score: {result.factuality.consistency_score:.2f}</p>
    <p>Claims Checked: {result.factuality.claims_checked}</p>
    
    <h3>Details</h3>
    <pre>{result.chain_of_thought}</pre>
</body>
</html>
        """.strip()
    else:
        # Default text format
        return f"""Clinical Note Quality Assessment
=================================

Overall Grade: {result.overall_grade}
Overall Score: {result.hybrid_score}

PDQI Analysis:
  Average: {result.pdqi.average:.2f}
  Model: {result.pdqi.model_provenance}
  Summary: {result.pdqi.summary}

Heuristic Analysis:
  Composite Score: {result.heuristic.composite_score:.2f}
  Word Count: {result.heuristic.word_count}

Factuality Analysis:
  Consistency Score: {result.factuality.consistency_score:.2f}
  Claims Checked: {result.factuality.claims_checked}

Chain of Thought:
{result.chain_of_thought}
"""


@app.command()
def grade(
    input_path: Optional[str] = typer.Argument(None, help="File path to grade (or '-' for stdin)"),
    output_format: str = typer.Option("text", "--output", "-o", help="Output format: text, json, html"),
    precision: str = typer.Option("medium", "--precision", "-p", help="Model precision: low, medium, high"),
    transcript: Optional[str] = typer.Option(None, "--transcript", "-t", help="Path to transcript file"),
    output_file: Optional[str] = typer.Option(None, "--output-file", "-f", help="Write output to file"),
) -> None:
    """Grade a clinical note from file or stdin."""
    
    if not input_path or input_path == "-":
        # Read from stdin
        if console:
            console.print("Reading from stdin... (press Ctrl+D when done)")
        note_content = sys.stdin.read()
    else:
        # Read from file
        try:
            note_content = Path(input_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            if console:
                console.print(f"[red]Error: File not found: {input_path}[/red]")
            else:
                print(f"Error: File not found: {input_path}")
            raise typer.Exit(1)
        except Exception as e:
            if console:
                console.print(f"[red]Error reading file: {e}[/red]")
            else:
                print(f"Error reading file: {e}")
            raise typer.Exit(1)
    
    # Read transcript if provided
    transcript_content = ""
    if transcript:
        try:
            transcript_content = Path(transcript).read_text(encoding="utf-8")
        except Exception as e:
            if console:
                console.print(f"[yellow]Warning: Could not read transcript: {e}[/yellow]")
            else:
                print(f"Warning: Could not read transcript: {e}")
    
    # Grade the note
    try:
        grader = ClinicalNoteGrader()
        
        if console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Grading clinical note...", total=None)
                result = grader.grade(note_content, transcript_content, precision)
        else:
            print("Grading clinical note...")
            result = grader.grade(note_content, transcript_content, precision)
        
        # Format output
        formatted_output = _format_output(result, output_format)
        
        # Write output
        if output_file:
            Path(output_file).write_text(formatted_output, encoding="utf-8")
            if console:
                console.print(f"[green]Results written to {output_file}[/green]")
            else:
                print(f"Results written to {output_file}")
        else:
            print(formatted_output)
            
    except Exception as e:
        if console:
            console.print(f"[red]Error during grading: {e}[/red]")
        else:
            print(f"Error during grading: {e}")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    print("Clinical Note Quality Grader v2.0.0-dev")


def main() -> None:
    """Entry point for the CLI application."""
    if typer is None:
        print("Error: typer and rich are required for CLI functionality.")
        print("Install with: pip install typer rich")
        sys.exit(1)
    
    app()


if __name__ == "__main__":
    main() 