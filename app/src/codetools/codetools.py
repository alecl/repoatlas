import mmap
import os
from re import Pattern
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

import puremagic

from .ignore import IgnorePatternManager
from .logging import logger


class FileContentsSearchConfig(NamedTuple):
    """Configuration for searching file contents with multiple criteria types.

    This class is exclusively used for matching file CONTENTS (not filenames).
    A file matches if ANY of the specified criteria types match its contents (OR logic).
    Within each criteria type, a file matches if ANY specific pattern matches (also OR logic).

    Attributes:
        contains: Optional[List[str]] = None
            List of substrings to search for in file contents.
            A file matches if ANY of these strings is found.

        regex: Optional[List[Pattern]] = None
            List of compiled regex patterns to apply to file contents (not filenames).
            A file matches if ANY of these patterns match the file contents.

        file_type_map: Optional[Dict[str, Pattern]] = None
            File extension -> regex map. This checks if a file's extension is in the map,
            and if so, applies the corresponding regex pattern to the file contents.
    """

    contains: list[str] | None = None
    regex: list[Pattern] | None = None
    file_type_map: dict[str, Pattern] | None = None


def is_binary_file(file_path: str, sample_size: int = 512) -> bool:
    """
    Determine if a file is binary.
    Uses known text file extensions and binary file extensions.
    If unknown, falls back to puremagic detection and a heuristic check.
    """
    logger.debug(f"Checking if file is binary: {file_path}")

    known_text_ext = {
        ".astro",  # Astro framework files
        ".aspx",
        ".babel",
        ".babelrc",
        ".bash",
        ".bashrc",
        ".bat",
        ".c",
        ".cc",
        ".cfg",
        ".clj",  # Clojure
        ".cmake",
        ".conf",
        ".config",
        ".cpp",
        ".cpy",  # Cython files
        ".cs",
        ".cshtml",
        ".csproj",  # C# project file
        ".css",
        ".csv",
        ".csx",  # C# script
        ".dart",  # Dart language (Flutter)
        ".dockerfile",
        ".dockerignore",
        ".editorconfig",
        ".ejs",  # Embedded JavaScript templates
        ".elm",  # Elm language
        ".env",
        ".erb",  # Ruby templating
        ".eslintignore",
        ".eslintrc",
        ".ex",  # Elixir
        ".exs",  # Elixir script
        ".flake8",  # Python linter config
        ".fs",  # F#
        ".fsproj",  # F# project file
        ".gemspec",  # Ruby gem specification
        ".gitattributes",
        ".gitconfig",
        ".github",  # GitHub specific configs
        ".gitignore",
        ".gitkeep",
        ".go",
        ".gradle",  # Gradle build system
        ".graphql",  # GraphQL schema files
        ".groovy",  # Groovy language
        ".h",  # C/C++ header
        ".haml",  # HTML abstraction markup language
        ".hbs",  # Handlebars templates
        ".hs",  # Haskell
        ".htm",
        ".html",
        ".ini",
        ".ipynb",  # Jupyter notebook
        ".jade",  # Jade/Pug template language (older name)
        ".java",
        ".jl",  # Julia language
        ".js",
        ".json",
        ".jsx",
        ".kt",  # Kotlin
        ".kts",  # Kotlin script
        ".less",
        ".liquid",  # Liquid templating
        ".lua",  # Lua language
        ".m",  # Objective-C/MATLAB
        ".make",
        ".makefile",
        ".markdown",
        ".md",
        ".mdx",  # Markdown with JSX
        ".mjs",  # ES modules JavaScript
        ".ml",  # OCaml
        ".nim",  # Nim language
        ".njk",  # Nunjucks templates
        ".npmignore",
        ".npmrc",
        ".nuspec",  # NuGet package spec
        ".php",
        ".pl",  # Perl
        ".postcss",  # PostCSS config
        ".prettierignore",
        ".prettierrc",
        ".ps1",  # PowerShell
        ".pug",  # Pug template language
        ".py",
        ".pyi",  # Python interface files
        ".pyw",
        ".r",  # R language
        ".rake",  # Ruby make
        ".razor",
        ".rb",
        ".rc",  # Resource config files
        ".rs",  # Rust
        ".rst",  # reStructuredText
        ".sass",
        ".scala",  # Scala language
        ".scss",
        ".sh",  # Shell script
        ".sol",  # Solidity (blockchain)
        ".sql",
        ".styl",  # Stylus CSS preprocessor
        ".svelte",  # Svelte component files
        ".swift",
        ".tailwind.config.js",  # Tailwind CSS config file
        ".tf",  # Terraform
        ".tfvars",  # Terraform variables
        ".tpl",  # Template files
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".vb",
        ".vbproj",  # Visual Basic project
        ".vim",  # Vim config
        ".vue",  # Vue.js component files
        ".wat",
        ".xaml",  # XAML for .NET
        ".xhtml",  # XHTML
        ".xml",
        ".xsd",  # XML Schema
        ".xsl",  # XSLT
        ".yaml",
        ".yml",
        ".zsh",  # Z shell script
        ".zshrc",  # Z shell config
    }
    known_binary_ext = {".class", ".exe", ".dll", ".so", ".bin", ".img", ".o"}
    ext = os.path.splitext(file_path)[1].lower()
    if ext in known_text_ext:
        return False
    if ext in known_binary_ext:
        return True
    try:
        mime_type = puremagic.from_file(file_path, mime=True)
        if not mime_type.startswith("text/"):
            return True
    except Exception:
        pass
    try:
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)
            if b"\0" in sample:
                return True
            # Fallback heuristic: check if the sample contains non-ASCII characters
            if any(byte > 127 for byte in sample):
                return True
    except Exception:
        return True
    return False


def file_contains(
    filepath: str,
    search_config: str | FileContentsSearchConfig | None = None,
    size_threshold: int = 1_000_000,
) -> bool:
    """Check if file contents match specified patterns using an appropriate method based on file size.

    Args:
        filepath (str): The path to the file.
        search_config (Union[str, FileContentsSearchConfig, None]): Either a string to search for or a
            FileContentsSearchConfig object. If None, the function will return True for all non-binary files.
        size_threshold (int, optional): The file size threshold in bytes. Defaults to 1_000_000.

    Returns:
        bool: True if ANY of the search criteria match the file's contents (OR logic across all criteria types),
              False otherwise. Within each criteria type (contains, regex, file_type_map),
              OR logic is also used - so if ANY pattern within that type matches, that criteria
              type is considered a match.

        Note: This function only checks file CONTENTS. It does not match patterns against filenames.
    """
    try:
        if is_binary_file(filepath):
            return False

        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return False

        # Handle legacy string input for backward compatibility
        if isinstance(search_config, str):
            search_config = FileContentsSearchConfig(contains=[search_config])
        elif search_config is None:
            return True  # No search criteria means all non-binary files match

        # Check if any criteria were specified
        if (
            not search_config.contains
            and not search_config.regex
            and not search_config.file_type_map
        ):
            return True  # SearchConfig with no criteria matches all files

        # Read the file content
        try:
            with open(filepath, "rb") as f:
                if file_size > size_threshold:
                    try:
                        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                            content_bytes = mm.read()
                    except (ValueError, OSError, AttributeError) as mmap_error:
                        logger.debug(f"mmap failed for {filepath}: {str(mmap_error)}")
                        f.seek(0)
                        content_bytes = f.read()
                else:
                    content_bytes = f.read()

                # Convert bytes to string if needed
                if isinstance(content_bytes, bytes):
                    content = content_bytes.decode("utf-8", errors="replace")
                else:
                    content = content_bytes
        except Exception as e:
            # Fallback to text mode if binary mode fails
            try:
                with open(filepath, errors="replace") as f:
                    content = f.read()
            except Exception as e2:
                logger.debug(f"Error reading file {filepath}: {str(e)} then {str(e2)}")
                return False

        # Check file_type_map if specified
        if search_config.file_type_map:
            file_ext = os.path.splitext(filepath)[1].lower()
            if file_ext in search_config.file_type_map:
                pattern = search_config.file_type_map[file_ext]
                if pattern.search(content):
                    return True

        # Check for substring matches if specified
        if search_config.contains:
            for substring in search_config.contains:
                if substring in content:
                    return True

        # Check for regex matches against content if specified
        if search_config.regex:
            for pattern in search_config.regex:
                if pattern.search(content):
                    return True

        # If we got here, none of the criteria matched
        return False

    except OSError as e:
        logger.debug(f"Error reading file {filepath}: {str(e)}")
        return False


def generate_file_trees(
    root_dir: str,
    search_config: str | FileContentsSearchConfig | None = None,
    additional_ignore_files: list[str] | None = None,
    additional_ignore_patterns: list[str] | None = None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Generate file and folder trees, respecting ignore rules defined in .gitignore/.aiexclude files.

    Args:
        root_dir (str): The root directory to start from.
        search_config (Union[str, FileContentsSearchConfig, None]): An optional search configuration to filter files.
            Can be a simple string (for backward compatibility) or a FileContentsSearchConfig object.
            When using FileContentsSearchConfig, OR logic is used - a file matches if ANY criteria matches.

            Note: FileContentsSearchConfig only matches file CONTENTS (not filenames).

        additional_ignore_files (Optional[List[str]]): Additional files to read for ignore patterns.
        additional_ignore_patterns (Optional[List[str]]): Additional patterns to ignore.

    Returns:
        Tuple[List[str], List[str], List[str], List[str]]:
            A tuple containing:
              - all_files: A list of non-ignored file paths relative to root_dir.
              - all_folders: A list of non-ignored folder paths relative to root_dir that
                contain at least one non-ignored file.
              - matching_files: A list of file paths that match the search configuration.
              - matching_folders: A list of folder paths containing files that match the search configuration.
    """
    # Create an IgnorePatternManager for the root directory
    logger.debug(f"Generating file trees for root directory: {root_dir}")
    ignore_manager = IgnorePatternManager(
        root_dir,
        additional_ignore_files=additional_ignore_files,
        additional_ignore_patterns=additional_ignore_patterns,
    )

    all_files = []
    all_folders = set()  # Use a set to avoid duplicates
    matching_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        logger.debug(f"Scanning directory: {dirpath}")

        # Filter dirnames in place to prevent walking into ignored directories
        dirnames[:] = [
            d for d in dirnames if not ignore_manager.should_ignore(os.path.join(dirpath, d))
        ]

        # Process non-ignored files
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if not ignore_manager.should_ignore(file_path):
                rel_file_path = os.path.relpath(file_path, root_dir)
                all_files.append(rel_file_path)

                # Also add the file's parent directory to all_folders
                parent_dir = os.path.dirname(rel_file_path)
                if parent_dir and parent_dir not in (".", ""):
                    all_folders.add(parent_dir)

                    # Add all parent directories
                    path_parts = parent_dir.split(os.sep)
                    current_path = ""
                    for part in path_parts:
                        current_path = os.path.join(current_path, part) if current_path else part
                        if current_path and current_path not in (".", ""):
                            all_folders.add(current_path)

                # If a search configuration is provided, check if the file contents match
                if search_config and file_contains(file_path, search_config):
                    matching_files.append(rel_file_path)

    # Calculate matching_folders based on matching files
    matching_folders = set()
    for file_path in matching_files:
        parent_dir = os.path.dirname(file_path)
        if parent_dir and parent_dir not in (".", ""):
            matching_folders.add(parent_dir)

            # Add all parent directories
            path_parts = parent_dir.split(os.sep)
            current_path = ""
            for part in path_parts:
                current_path = os.path.join(current_path, part) if current_path else part
                if current_path and current_path not in (".", ""):
                    matching_folders.add(current_path)

    # Convert sets to sorted lists
    all_files = sorted(all_files)
    all_folders = sorted(all_folders)
    matching_files = sorted(matching_files)
    matching_folders = sorted(matching_folders)

    logger.debug(f"All files: {all_files}")
    logger.debug(f"All folders: {all_folders}")
    logger.debug(f"Matching files: {matching_files}")
    logger.debug(f"Matching folders: {matching_folders}")

    return all_files, all_folders, matching_files, matching_folders


def merge_file_trees(
    files_to_add: list[str],
    all_files: list[str],
    all_folders: list[str],
    matching_files: list[str],
    matching_folders: list[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Merge additional files into existing file trees.

    Args:
        files_to_add: List of additional file paths to merge
        all_files: Existing list of all files
        all_folders: Existing list of all folders
        matching_files: Existing list of matching files
        matching_folders: Existing list of matching folders

    Returns:
        Tuple containing updated (all_files, all_folders, matching_files, matching_folders)
    """
    logger.debug("Merging %d additional files into file trees", len(files_to_add))

    # Create sets for efficient membership testing and deduplication
    all_files_set = set(all_files)
    all_folders_set = set(all_folders)
    matching_files_set = set(matching_files)
    matching_folders_set = set(matching_folders)

    for file_path in files_to_add:
        # Add file if not already present
        if file_path not in all_files_set:
            all_files_set.add(file_path)

            # Add parent directories to all_folders
            current_path = os.path.dirname(file_path)
            while current_path:
                if current_path not in all_folders_set and current_path not in (
                    ".",
                    "",
                ):
                    all_folders_set.add(current_path)
                current_path = os.path.dirname(current_path)

        # If file was in matching_files, ensure its folders are in matching_folders
        if file_path in matching_files_set:
            current_path = os.path.dirname(file_path)
            while current_path:
                if current_path not in matching_folders_set and current_path not in (
                    ".",
                    "",
                ):
                    matching_folders_set.add(current_path)
                current_path = os.path.dirname(current_path)

    # Convert back to sorted lists
    return (
        sorted(all_files_set),
        sorted(all_folders_set),
        sorted(matching_files_set),
        sorted(matching_folders_set),
    )
