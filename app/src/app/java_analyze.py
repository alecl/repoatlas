"""
Example usage of the Java Spring Analyzer.

This script demonstrates how to analyze Java Spring REST controller files
and extract useful information such as endpoints, service dependencies,
method calls, and their visualizations.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from app.src.codeanalyzer.code_analyzer_config import load_config_from_cli_arg

load_dotenv(override=True)

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.code_visualizer import CodeVisualizer

# Import from our modules
from app.src.codeanalyzer.models import (
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaClass,
    RestControllerClass,
    ServiceClass,
)


def setup_argparse() -> argparse.ArgumentParser:
    """Set up command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Analyze Java Spring files for controllers and endpoints"
    )
    parser.add_argument("path", nargs="+", help="Path to a Java file or directory to analyze")
    parser.add_argument(
        "--config",
        type=str,
        help=(
            "Path to configuration file (JSON5 with comments supported). "
            "See app/src/codeanalyzer/codeanalyzer_sample_config.json for an example."
        ),
    )
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Recursively analyze directories"
    )
    parser.add_argument("--dump", "-d", action="store_true", help="Dump class source")
    parser.add_argument(
        "--resolve-constants",
        "-rc",
        action="store_true",
        help="Resolve constant variables in class dump",
    )
    parser.add_argument(
        "--constants", "-c", help="Path to a JSON file containing constant mappings"
    )
    parser.add_argument("--output", "-o", help="Path to write analysis results (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "mermaid-class", "mermaid-flow"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--search",
        "-s",
        nargs="+",
        help="Search for classes or endpoints by name, path, package, or endpoint substring",
    )
    parser.add_argument(
        "--search-type",
        choices=["name", "path", "package", "endpoint"],
        help="Type of search to perform (default: name)",
    )
    parser.add_argument(
        "--base-path",
        nargs="+",
        help="Base path(s) to strip from endpoint prefixes before searching (only for --search-type endpoint)",
    )
    return parser


def load_constants(constants_path: str) -> dict[str, str]:
    """
    Load constants from a JSON file.

    Args:
        constants_path: Path to the JSON file containing constant mappings

    Returns:
        Dictionary mapping constant variable names to their values
    """
    try:
        with open(constants_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading constants file: {e}", file=sys.stderr)
        return {}


def search_classes(
    analyzer: JavaAnalyzer,
    search_terms: list[str],
    search_type: str,
    base_paths: list[str] | None = None,
) -> list[JavaClass]:
    """
    Search for classes or endpoints using different criteria.

    Args:
        analyzer: The JavaAnalyzer containing the classes
        search_terms: The terms to search for
        search_type: The type of search ('name', 'path', 'package', 'endpoint')
        base_path: The base path to strip from endpoints (for endpoint search)

    Returns:
        List of matching JavaClass objects
    """
    if search_type == "name":
        results = []
        for term in search_terms:
            results.extend(analyzer.find_class_by_name(term))
        return results
    elif search_type == "path":
        results = []
        for term in search_terms:
            # Try both absolute and relative paths
            cls = analyzer.find_class_by_path(term, is_relative=False)
            if cls:
                results.append(cls)
                continue
            cls = analyzer.find_class_by_path(term, is_relative=True)
            if cls:
                results.append(cls)
        return results
    elif search_type == "package":
        results = []
        for term in search_terms:
            results.extend(analyzer.find_class_by_package(term))
        return results
    elif search_type == "endpoint":
        return analyzer.find_classes_by_endpoint(search_terms, optional_base_paths=base_paths)
    else:
        print(f"Invalid search type: {search_type}", file=sys.stderr)
        return []


def format_output(analyzer: JavaAnalyzer, format_type: str) -> str:
    """
    Format the analysis results based on the selected format.

    Args:
        analyzer: The JavaAnalyzer containing the results
        format_type: The format type ('text', 'json', 'markdown', etc.)

    Returns:
        Formatted output string
    """
    classes = list(analyzer.classes.values())

    if format_type == "json":
        return CodeVisualizer.format_json(classes)
    elif format_type == "markdown":
        return CodeVisualizer.format_markdown(classes)
    elif format_type == "mermaid-class":
        return CodeVisualizer.format_mermaid_classdiagram(classes)
    elif format_type == "mermaid-flow":
        return CodeVisualizer.format_mermaid_flowchart(classes)
    else:  # default to text
        return CodeVisualizer.format_text(classes)


def write_output(output: str, output_path: str | None = None) -> None:
    """
    Write output to a file or stdout.

    Args:
        output: The output string to write
        output_path: Optional file path to write to
    """
    if output_path:
        with open(output_path, "w") as f:
            f.write(output)
    else:
        print(output)


def main() -> int:
    """Main entry point."""
    # Parse command line arguments
    parser = setup_argparse()
    args = parser.parse_args()

    # Usage checks for new search logic
    if args.search_type == "endpoint" and not args.base_path:
        print(
            "Error: --base-path is required when --search-type endpoint is used.",
            file=sys.stderr,
        )
        return 2
    if args.base_path and args.search_type != "endpoint":
        print(
            "Error: --base-path is only valid with --search-type endpoint.",
            file=sys.stderr,
        )
        return 2
    if args.search_type and not args.search:
        print("Error: --search-type requires --search.", file=sys.stderr)
        return 2

    # Load constants if provided
    constants = None
    if args.constants:
        constants = load_constants(args.constants)

    # Load configuration from CLI argument
    config = load_config_from_cli_arg(args.config)

    # Initialize the analyzer
    analyzer = JavaAnalyzer(config=config)
    if constants:
        analyzer.add_constants(constants)

    # Loop through each path and parse
    for path in args.path:
        try:
            if os.path.isfile(path):
                analyzer.parse_file(path)
            elif os.path.isdir(path):
                analyzer.parse_directory(path, recursive=args.recursive)
            else:
                print(f"Error: Path does not exist: {path}", file=sys.stderr)
        except Exception as e:
            print(f"Error processing path '{path}': {e}", file=sys.stderr)

    analyzer._resolve_all_references()

    # Search for specific classes or endpoints if requested
    if args.search:
        found_classes = search_classes(
            analyzer, args.search, args.search_type, base_paths=args.base_path
        )
        if found_classes:
            print(f"Found {len(found_classes)} matching classes:")
            for cls in found_classes:
                print(f"  {cls.name} ({cls.package})")
            # Replace analyzer's classes with just the found ones for output
            filtered_analyzer = JavaAnalyzer(config=config)
            for cls in found_classes:
                filtered_analyzer.classes[cls.fully_qualified_name] = cls
            analyzer = filtered_analyzer
        else:
            print(f"No classes found matching: {args.search}")
            return 1

    # Display analysis results
    # Check if we have classes to analyze
    if not analyzer.classes:
        print("No Java classes were found for analysis")
        return 1

    # Format output based on selected format
    output = format_output(analyzer, args.format)

    # Write output
    write_output(output, args.output)

    if args.dump:
        class_dump: dict[str, str] = analyzer.dump_classes_to_string(
            analyzer.get_classes_by_category_with_dependencies(ClassCategory.CONTROLLER),
            resolve_constants=True,
        )
        # Print the class dump
        print("\n=== Class Dump ===")
        for class_name, class_info in class_dump.items():
            print(f"{class_name}:")
            print(class_info)

    return 0


if __name__ == "__main__":
    sys.exit(main())
