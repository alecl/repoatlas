import os
from typing import List, Optional, Union

from . import codetools
from .logging import logger


def merge_code_from_files(
    file_list: list[str],
    root_dir: str,
    include_file_tree: bool,
    folder_tree: list[str] | None = None,
    include_line_numbers: bool = False,
    include_folder_tree: bool = False,
) -> str:
    """
    Merge code from a list of files.

    Args:
        file_list (List[str]): List of file paths relative to root_dir.
        root_dir (str): The root directory for file paths.
        include_file_tree (bool): Whether to include a file tree in the output.
        folder_tree (Optional[List[str]]): An optional list of folder paths to include.
        include_line_numbers (bool): Whether to include left zero-padded 4-digit line numbers.
        include_folder_tree (bool): Whether to include the folder tree in the output.

    Returns:
        str: The merged code output.
    """
    logger.debug("Merging code from files...")
    output = []

    # Include folder tree if requested and if folder_tree is not empty
    if include_folder_tree and folder_tree:
        # Filter out any empty strings from folder_tree
        clean_folders = [f for f in folder_tree if f and f.strip()]

        if clean_folders:  # Only add the section if there are folders to include
            logger.debug(f"Including folder tree in output. Folders: {clean_folders}")
            output.append("----- FOLDER TREE -----")
            for folder in clean_folders:
                output.append(folder)
            output.append("")

    if include_file_tree:
        logger.debug("Including file tree in output.")
        output.append("----- FILE TREE -----")
        for f in file_list:
            output.append(f)
        output.append("")

    output.append("----- MERGED CODE -----")
    for f in file_list:
        full_path = os.path.join(root_dir, f)
        output.append(f"--- {f} ---")
        try:
            with open(full_path) as file:
                lines = file.readlines()
        except Exception as e:
            lines = [f"// Could not read {f}: {str(e)}\n"]

        if include_line_numbers:
            numbered_lines = []
            for idx, line in enumerate(lines, start=1):
                numbered_lines.append(f"{idx:04d}: {line.rstrip()}")
            lines = numbered_lines
        else:
            lines = [line.rstrip() for line in lines]

        output.extend(lines)
        output.append("")

    return "\n".join(output)


def merge_code_from_root(
    root_dir: str,
    search_term: str | codetools.FileContentsSearchConfig | None = None,
    include_file_tree: bool = False,
    include_folder_tree: bool = False,
    include_line_numbers: bool = False,
) -> str:
    """
    Merge code from files obtained from the given root directory.

    This function calls generate_file_trees to get the file tree.
    If search_term is provided, matching files are used; otherwise all files are used.
    Folder tree and file tree may be optionally included in the output.

    Args:
        root_dir (str): The root directory to search.
        search_term (Union[str, SearchConfig, None]): Optional search term or search config to filter files.
            When using SearchConfig, a file matches if ANY criteria matches (OR logic).
        include_file_tree (bool): Whether to include file tree in output.
        include_folder_tree (bool): Whether to include folder tree in output.
        include_line_numbers (bool): Whether to display line numbers.

    Returns:
        str: The merged code output.
    """
    all_files, all_folders, matching_files, matching_folders = codetools.generate_file_trees(
        root_dir, search_term
    )

    # Log what was found
    logger.debug(f"Found {len(all_files)} files, {len(all_folders)} folders")
    logger.debug(
        f"Matching files: {len(matching_files)}, Matching folders: {len(matching_folders)}"
    )

    # Determine which files and folders to use based on search term
    if search_term is not None:  # Use is not None to handle empty strings or other falsy values
        file_list = matching_files
        folder_tree = matching_folders
    else:
        file_list = all_files
        folder_tree = all_folders

    # Clean folders - ensure no empty strings
    folder_tree = [f for f in folder_tree if f and f.strip()]

    return merge_code_from_files(
        file_list,
        root_dir,
        include_file_tree,
        folder_tree,
        include_line_numbers,
        include_folder_tree,
    )
