#!/usr/bin/env python3
"""
Debug script for code_context_tools

This script provides a simple CLI interface to test the code context generation
functionality without using the MCP server.
"""

import argparse
import importlib.util
import json
import os
import sys
import traceback
from typing import Dict, List, Optional

# Print debugging information about the Python environment
print("=" * 50)
print("DEBUGGING INFORMATION:")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")
print("sys.path (Python's import search paths):")
for i, path in enumerate(sys.path):
    print(f"  {i}: {path}")

# Print module information
print("\nModule information:")
print(f"__name__: {__name__}")
print(f"__package__: {__package__}")
print(f"__file__: {__file__}")

# Try to find specific modules
print("\nChecking for specific modules:")
try:
    import app

    print(f"app module found at: {app.__file__}")
except ImportError as e:
    print(f"app module not found: {e}")

try:
    import codetools

    print(f"codetools module found at: {codetools.__file__}")
except ImportError as e:
    print(f"codetools module not found: {e}")

# Check if specific files exist
print("\nChecking for specific files:")
paths_to_check = [
    os.path.join(os.getcwd(), "experimental", "code_context_tools.py"),
    os.path.join(os.getcwd(), "app", "src", "codetools", "codetools.py"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "code_context_tools.py"),
]
for path in paths_to_check:
    print(f"Checking {path}: {'EXISTS' if os.path.exists(path) else 'NOT FOUND'}")

print("=" * 50)

# Add the parent directory to sys.path to allow importing the modules
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# from app.src.app.code_context_tools import (
#        SecurityError,
#        generate_code_context,
#        merge_code_context,
# )

# Get absolute paths to the modules we need
code_context_tools_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "code_context_tools.py")
)
print(f"Loading code_context_tools from: {code_context_tools_path}")

# Load the code_context_tools module directly
spec = importlib.util.spec_from_file_location("code_context_tools", code_context_tools_path)
code_context_tools = importlib.util.module_from_spec(spec)
sys.modules["code_context_tools"] = code_context_tools
spec.loader.exec_module(code_context_tools)

# Now import the specific functions we need
SecurityError = code_context_tools.SecurityError
generate_code_context = code_context_tools.generate_code_context
merge_code_context = code_context_tools.merge_code_context


def parse_args():
    parser = argparse.ArgumentParser(description="Debug tool for code context generation")
    parser.add_argument("root_dir", help="Root directory to scan for code context generation")
    parser.add_argument(
        "--search", "-s", help="Search term to filter files by content", default=None
    )
    parser.add_argument(
        "--regex", "-r", action="store_true", help="Treat search term as regex pattern"
    )
    parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        help="File extensions to limit search to (e.g. .py .js)",
        default=None,
    )
    parser.add_argument(
        "--ignore-files",
        "-i",
        nargs="+",
        help="Additional files containing ignore patterns",
        default=None,
    )
    parser.add_argument(
        "--ignore-patterns",
        "-p",
        nargs="+",
        help="Additional patterns to ignore",
        default=None,
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate preview instead of full context",
        default=True,
    )
    parser.add_argument(
        "--max-folders",
        type=int,
        help="Maximum number of folders to include in preview",
        default=10,
    )
    parser.add_argument(
        "--max-files-per-folder",
        type=int,
        help="Maximum number of files to show per folder in preview",
        default=3,
    )
    parser.add_argument(
        "--merge",
        "-m",
        action="store_true",
        help="Merge code from matching files",
        default=False,
    )
    parser.add_argument(
        "--file-tree",
        action="store_true",
        help="Include file tree in merged output",
        default=True,
    )
    parser.add_argument(
        "--folder-tree",
        action="store_true",
        help="Include folder tree in merged output",
        default=False,
    )
    parser.add_argument(
        "--line-numbers",
        action="store_true",
        help="Include line numbers in merged code",
        default=False,
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for merged code (default: stdout)",
        default=None,
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        # Normalize the path
        root_dir = os.path.abspath(os.path.expanduser(args.root_dir))

        # Generate code context
        context = generate_code_context(
            root_dir=root_dir,
            search_term=args.search,
            use_regex=args.regex,
            file_extensions=args.extensions,
            additional_ignore_files=args.ignore_files,
            additional_ignore_patterns=args.ignore_patterns,
            preview_mode=args.preview,
            max_preview_folders=args.max_folders,
            max_files_per_folder=args.max_files_per_folder,
        )

        # Print preview information
        if args.preview:
            print(f"Total matching folders: {context.get('total_matching_folders', 0)}")
            print(f"Total matching files: {context.get('total_matching_files', 0)}")
            print("\nFolder preview:")
            for folder, data in context.get("folders", {}).items():
                print(f"\n{folder}/")
                for file in data.get("sample_files", []):
                    print(f"  - {file}")
                if data.get("total_files", 0) > len(data.get("sample_files", [])):
                    print(
                        f"  ... and {data.get('total_files') - len(data.get('sample_files', []))} more files"
                    )

            if context.get("truncated", False):
                print(f"\n... and {context.get('folders_not_shown', 0)} more folders")
        else:
            print(f"Matching folders: {len(context.get('matching_folders', []))}")
            print(f"Matching files: {len(context.get('matching_files', []))}")

        # Merge code if requested
        if args.merge:
            # Extract matching files and folders
            if "matching_files" in context:
                matching_files = context["matching_files"]
                matching_folders = context.get("matching_folders", [])
            else:
                # Extract from preview data
                matching_files = []
                matching_folders = list(context.get("folders", {}).keys())
                for folder, folder_data in context.get("folders", {}).items():
                    for file in folder_data.get("sample_files", []):
                        if folder == ".":
                            matching_files.append(file)
                        else:
                            matching_files.append(f"{folder}/{file}")

            # Merge the code
            merged_code = merge_code_context(
                root_dir=root_dir,
                matching_files=matching_files,
                matching_folders=matching_folders,
                include_file_tree=args.file_tree,
                include_folder_tree=args.folder_tree,
                include_line_numbers=args.line_numbers,
            )

            # Output the merged code
            if args.output:
                with open(args.output, "w") as f:
                    f.write(merged_code)
                print(f"\nMerged code written to {args.output}")
            else:
                print("\n" + "=" * 80)
                print("MERGED CODE:")
                print("=" * 80)
                print(merged_code)

    except SecurityError as e:
        print(f"Security Error: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Directory Not Found: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    except NotADirectoryError as e:
        print(f"Not A Directory: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    except PermissionError as e:
        print(f"Permission Denied: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
