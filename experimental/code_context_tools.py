"""
Code Context Tools for MCP

This module provides utilities for generating code context for LLMs
by leveraging the codetools package functionality.
"""

import os
import pathlib
import re
from typing import Dict, List, Optional, Tuple, Union

from app.src.codetools.codetools import FileContentsSearchConfig, generate_file_trees
from app.src.codetools.merge import merge_code_from_files

# Define sensitive directories that should not be accessed
SENSITIVE_DIRECTORIES = [
    ".aws",  # AWS credentials
    ".ssh",  # SSH keys
    ".gnupg",  # GPG keys
    ".config",  # Configuration files that may contain secrets
    ".kube",  # Kubernetes config
    ".azure",  # Azure credentials
    ".gcloud",  # Google Cloud credentials
    ".docker",  # Docker credentials
    ".npm",  # NPM credentials
    ".gem",  # Ruby gems credentials
    ".netrc",  # .netrc file with credentials
    ".git-credentials",  # Git credentials
    "etc/shadow",  # System password file
    "etc/passwd",  # System user information
    "etc/sudoers",  # Sudo configuration
    "/proc",  # Process information
    "/sys",  # System information
    "/var/log",  # System logs
    "/var/spool",  # System queues
    "/root",  # Root user home directory
    "/private",  # macOS private directory
    "Library/Keychains",  # macOS keychains
    "Credentials",  # Generic credentials directory
    "secrets",  # Generic secrets directory
    "passwords",  # Generic passwords directory
    "tokens",  # Generic tokens directory
    "keys",  # Generic keys directory
]


# --- Security and validation utilities ---


def generate_code_context(
    root_dir: str,
    search_term: str | None = None,
    use_regex: bool = False,
    file_extensions: list[str] | None = None,
    additional_ignore_files: list[str] | None = None,
    additional_ignore_patterns: list[str] | None = None,
    preview_mode: bool = True,
    max_preview_folders: int = 10,
    max_files_per_folder: int = 3,
) -> dict[str, list[str] | dict]:
    """
    Generate code context information for a given directory with optional filtering.

    Args:
        root_dir: The root directory to scan
        search_term: Optional text to search for in file contents
        use_regex: Whether to treat search_term as a regex pattern
        file_extensions: Optional list of file extensions to limit search to
        additional_ignore_files: Additional files containing ignore patterns
        additional_ignore_patterns: Additional patterns to ignore
        preview_mode: Whether to return a preview of matching folders
        max_preview_folders: Maximum number of folders to include in preview
        max_files_per_folder: Maximum number of files to show per folder

    Returns:
        Dictionary with matching folders and preview information

    Raises:
        SecurityError: If the root_dir contains a sensitive directory
        FileNotFoundError: If the root_dir does not exist
        NotADirectoryError: If the root_dir is not a directory
        PermissionError: If the root_dir is not readable
    """
    # Validate directory access
    validate_directory_access(root_dir)

    # Create search configuration
    search_config = None
    if search_term:
        if use_regex:
            pattern = re.compile(search_term)
            if file_extensions:
                # Create a file extension -> regex map
                file_type_map = {ext.lower(): pattern for ext in file_extensions}
                search_config = FileContentsSearchConfig(file_type_map=file_type_map)
            else:
                search_config = FileContentsSearchConfig(regex=[pattern])
        else:
            search_config = FileContentsSearchConfig(contains=[search_term])

    # Generate file trees
    _, _, matching_files, matching_folders = generate_file_trees(
        root_dir, search_config, additional_ignore_files, additional_ignore_patterns
    )

    # Create result
    if preview_mode:
        result = preview_matching_folders(
            matching_folders, matching_files, max_preview_folders, max_files_per_folder
        )
    else:
        result = {
            "matching_folders": matching_folders,
            "matching_files": matching_files,
        }

    return result


def generate_context_from_directory(
    root_dir: str,
    search_term: str | None = None,
    use_regex: bool = False,
    file_extensions: list[str] | None = None,
    include_file_tree: bool = True,
    include_folder_tree: bool = False,
    include_line_numbers: bool = False,
    max_files: int | None = None,
) -> str:
    """
    Generate code context from a directory in a single operation.
    This is a convenience function that combines file tree generation
    and code merging into a single call.
    Args:
        root_dir: The root directory to scan
        search_term: Optional text to search for in file contents
        use_regex: Whether to treat search_term as a regex pattern
        file_extensions: Optional list of file extensions to limit search to
        include_file_tree: Whether to include the file tree in the output
        include_folder_tree: Whether to include the folder tree in the output
        include_line_numbers: Whether to include line numbers in the code
        max_files: Optional maximum number of files to include
    Returns:
        Merged code as a string
    """
    # Validate directory access
    validate_directory_access(root_dir)

    # Create search configuration
    search_config = None
    if search_term:
        if use_regex:
            pattern = re.compile(search_term)
            if file_extensions:
                # Create a file extension -> regex map
                file_type_map = {ext.lower(): pattern for ext in file_extensions}
                search_config = FileContentsSearchConfig(file_type_map=file_type_map)
            else:
                search_config = FileContentsSearchConfig(regex=[pattern])
        else:
            search_config = FileContentsSearchConfig(contains=[search_term])

    # Generate file trees
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        root_dir, search_config
    )

    # Determine which files to use
    if search_term:
        file_list = matching_files
        folder_tree = matching_folders
    else:
        file_list = all_files
        folder_tree = all_folders

    # Apply max_files limit if specified
    if max_files and len(file_list) > max_files:
        file_list = file_list[:max_files]

    # Merge the code
    return merge_code_from_files(
        file_list,
        root_dir,
        include_file_tree,
        folder_tree,
        include_line_numbers,
        include_folder_tree,
    )


def add_files_to_context(
    existing_files: list[str],
    additional_files: list[str],
    all_folders: list[str],
    root_dir: str,
    include_file_tree: bool = True,
    include_folder_tree: bool = False,
    include_line_numbers: bool = False,
) -> str:
    """
    Add additional files to an existing context.
    Args:
        existing_files: List of files already in the context
        additional_files: List of additional files to add
        all_folders: List of folders in the context
        root_dir: The root directory for file paths
        include_file_tree: Whether to include the file tree in the output
        include_folder_tree: Whether to include the folder tree in the output
        include_line_numbers: Whether to include line numbers in the code
    Returns:
        Updated merged code as a string
    """
    # Validate directory access
    validate_directory_access(root_dir)

    # Combine file lists, removing duplicates
    combined_files = list(set(existing_files + additional_files))

    # Merge the code
    return merge_code_from_files(
        combined_files,
        root_dir,
        include_file_tree,
        all_folders,
        include_line_numbers,
        include_folder_tree,
    )


def create_advanced_search_config(
    contains: list[str] | None = None,
    regex_patterns: list[str] | None = None,
    file_extensions: list[str] | None = None,
) -> FileContentsSearchConfig:
    """
    Create a more advanced search configuration for file filtering.
    Args:
        contains: List of strings to search for in file contents
        regex_patterns: List of regex patterns to search for in file contents
        file_extensions: List of file extensions to apply regex patterns to
    Returns:
        FileContentsSearchConfig object
    """
    # Compile regex patterns if provided
    compiled_patterns = None
    if regex_patterns:
        compiled_patterns = [re.compile(pattern) for pattern in regex_patterns]

    # Create file type map if extensions and patterns are provided
    file_type_map = None
    if file_extensions and regex_patterns:
        pattern = re.compile("|".join(f"({p})" for p in regex_patterns))
        file_type_map = {ext.lower(): pattern for ext in file_extensions}

    # Create and return the search config
    return FileContentsSearchConfig(
        contains=contains, regex=compiled_patterns, file_type_map=file_type_map
    )


class SecurityError(Exception):
    """Exception raised for security-related issues."""

    pass


def is_sensitive_directory(path: str) -> bool:
    """
    Check if a path contains or is a sensitive directory.

    Args:
        path: The path to check

    Returns:
        bool: True if the path contains a sensitive directory, False otherwise
    """
    # Normalize the path to handle different path formats
    norm_path = os.path.normpath(path).lower()

    # Check if the path contains any sensitive directory
    for sensitive_dir in SENSITIVE_DIRECTORIES:
        sensitive_pattern = os.path.sep + sensitive_dir.lower()
        if sensitive_pattern in norm_path or norm_path.startswith(sensitive_dir.lower()):
            return True

    # Check for home directory sensitive paths
    home_dir = os.path.expanduser("~")
    if path.startswith(home_dir):
        rel_path = os.path.relpath(path, home_dir)
        for sensitive_dir in SENSITIVE_DIRECTORIES:
            if (
                rel_path.startswith(sensitive_dir.lower())
                or os.path.sep + sensitive_dir.lower() in rel_path.lower()
            ):
                return True

    return False


def validate_directory_access(path: str) -> None:
    """
    Validate that a directory is safe to access.

    Args:
        path: The path to validate

    Raises:
        SecurityError: If the path contains a sensitive directory
    """
    if is_sensitive_directory(path):
        raise SecurityError(
            f"Access to sensitive directory '{path}' is not allowed for security reasons"
        )

    # Also check if the path exists and is accessible
    if not os.path.exists(path):
        raise FileNotFoundError(f"Directory '{path}' does not exist")

    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path '{path}' is not a directory")

    # Check if we have read permissions
    if not os.access(path, os.R_OK):
        raise PermissionError(f"No read permission for directory '{path}'")


def preview_matching_folders(
    matching_folders: list[str],
    matching_files: list[str],
    max_folders: int = 10,
    max_files_per_folder: int = 3,
) -> dict[str, list[str] | dict[str, list[str] | int]]:
    """
    Create a preview of matching folders with sample files.

    Args:
        matching_folders: List of folder paths that match the search criteria
        matching_files: List of file paths that match the search criteria
        max_folders: Maximum number of folders to include in preview
        max_files_per_folder: Maximum number of files to show per folder

    Returns:
        Dictionary with folder preview information
    """
    # Group files by folder
    folder_files = {}
    for file_path in matching_files:
        folder = os.path.dirname(file_path)
        if not folder:
            folder = "."  # Root directory

        if folder not in folder_files:
            folder_files[folder] = []
        folder_files[folder].append(os.path.basename(file_path))

    # Create preview data
    preview_data = {
        "total_matching_folders": len(matching_folders),
        "total_matching_files": len(matching_files),
        "folders": {},
    }

    # Add folder previews (limited to max_folders)
    for folder in sorted(matching_folders)[:max_folders]:
        files_in_folder = folder_files.get(folder, [])
        preview_data["folders"][folder] = {
            "sample_files": sorted(files_in_folder)[:max_files_per_folder],
            "total_files": len(files_in_folder),
        }

    # Add truncation indicator if needed
    if len(matching_folders) > max_folders:
        preview_data["truncated"] = True
        preview_data["folders_not_shown"] = len(matching_folders) - max_folders

    return preview_data


def merge_code_context(
    root_dir: str,
    matching_files: list[str],
    matching_folders: list[str] | None = None,
    include_file_tree: bool = True,
    include_folder_tree: bool = False,
    include_line_numbers: bool = False,
) -> str:
    """
    Merge code from matching files into a single context string.

    Args:
        root_dir: The root directory for file paths
        matching_files: List of file paths that match the search criteria
        matching_folders: Optional list of folder paths that match the search criteria
        include_file_tree: Whether to include the file tree in the output
        include_folder_tree: Whether to include the folder tree in the output
        include_line_numbers: Whether to include line numbers in the code

    Returns:
        Merged code as a string

    Raises:
        SecurityError: If the root_dir contains a sensitive directory
        FileNotFoundError: If the root_dir does not exist
        NotADirectoryError: If the root_dir is not a directory
        PermissionError: If the root_dir is not readable
    """
    # Validate directory access
    validate_directory_access(root_dir)

    # Validate that none of the files are in sensitive directories
    for file_path in matching_files:
        full_path = os.path.join(root_dir, file_path)
        if is_sensitive_directory(os.path.dirname(full_path)):
            raise SecurityError(
                f"Access to sensitive file '{full_path}' is not allowed for security reasons"
            )
    return merge_code_from_files(
        matching_files,
        root_dir,
        include_file_tree,
        matching_folders,
        include_line_numbers,
        include_folder_tree,
    )
