import os
import re

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from app.src.codetools.codetools import FileContentsSearchConfig
from app.src.codetools.merge import merge_code_from_files, merge_code_from_root


@pytest.fixture
def fs(monkeypatch):
    """Setup a fake filesystem for testing."""
    with Patcher() as patcher:
        # Create the basic directory structure
        patcher.fs.create_dir("/project")
        patcher.fs.create_dir("/project/subdir")

        # Create ignore files with proper formatting
        # Put the subdir ignore pattern in the root .gitignore to make sure it's applied
        patcher.fs.create_file(
            "/project/.gitignore", contents="ignore_me.txt\nsubdir/ignore_sub.txt\n"
        )
        patcher.fs.create_file("/project/.aiexclude", contents="exclude_this.log\n")

        # Create test files with text content
        patcher.fs.create_file("/project/file1.txt", contents="line1\nline2")
        patcher.fs.create_file(
            "/project/file2.txt", contents="This file contains SearchTerm to find"
        )
        patcher.fs.create_file(
            "/project/subdir/file3.txt", contents="Another file with SearchTerm content"
        )
        patcher.fs.create_file("/project/subdir/file4.txt", contents="No match here.")

        # Files that should be ignored
        patcher.fs.create_file("/project/ignore_me.txt", contents="This should be ignored")
        patcher.fs.create_file("/project/exclude_this.log", contents="This should be excluded")
        patcher.fs.create_file("/project/subdir/ignore_sub.txt", contents="Ignored content")

        # Example binary file
        patcher.fs.create_file("/project/binary.bin", contents=b"\x00\x01\x02\x03")

        # We still need to patch puremagic.from_file since it doesn't work with pyfakefs
        import puremagic

        def mock_from_file(filepath, *args, **kwargs):
            """Mock for puremagic.from_file that works with test file extensions"""
            ext = os.path.splitext(filepath)[1].lower()
            if ext in [".txt", ".py", ".md", ".gitignore", ".aiexclude"]:
                return "text/plain"
            if ext == ".bin":
                return "application/octet-stream"
            return "application/octet-stream"

        # Use monkeypatch to patch puremagic.from_file
        monkeypatch.setattr(puremagic, "from_file", mock_from_file)

        yield patcher.fs


def parse_section(text, section_header):
    """
    Parse a section from the merged code output.

    Args:
        text (str): The text to parse
        section_header (str): The section header to look for

    Returns:
        list: Lines of text in the section, excluding the header and empty lines
    """
    lines = text.split("\n")
    section_start = -1
    section_end = len(lines)

    for i, line in enumerate(lines):
        if line == section_header:
            section_start = i + 1
        elif section_start > -1 and line.startswith("-----") and i > section_start:
            section_end = i
            break

    if section_start == -1:
        return []

    # Return non-empty lines
    return [line for line in lines[section_start:section_end] if line.strip()]


def test_merge_code_from_files(fs):
    """Test merging code from a list of files."""
    root_dir = "/project"
    file_list = ["file1.txt", "subdir/file3.txt"]
    folder_tree = ["subdir"]

    result = merge_code_from_files(
        file_list,
        root_dir,
        include_file_tree=True,
        folder_tree=folder_tree,
        include_line_numbers=True,
        include_folder_tree=True,
    )

    # Check that all required sections are present
    assert "----- FOLDER TREE -----" in result
    assert "----- FILE TREE -----" in result
    assert "----- MERGED CODE -----" in result

    # Check the folder tree section
    folder_section = parse_section(result, "----- FOLDER TREE -----")
    assert folder_section == ["subdir"]

    # Check the file tree section
    file_section = parse_section(result, "----- FILE TREE -----")
    assert "file1.txt" in file_section
    assert "subdir/file3.txt" in file_section

    # Check that line numbers are present
    assert "0001:" in result


def test_merge_code_without_folder_tree(fs):
    """Test merging code without including the folder tree."""
    root_dir = "/project"
    file_list = ["file1.txt", "subdir/file3.txt"]
    folder_tree = ["subdir"]

    result = merge_code_from_files(
        file_list,
        root_dir,
        include_file_tree=True,
        folder_tree=folder_tree,
        include_line_numbers=True,
        include_folder_tree=False,  # Explicitly not including folder tree
    )

    # Check that folder tree is not present
    assert "----- FOLDER TREE -----" not in result
    # Check other sections are present
    assert "----- FILE TREE -----" in result
    assert "----- MERGED CODE -----" in result


def test_merge_code_from_root(fs):
    """Test merging code from a root directory."""
    root_dir = "/project"

    # Now run the merge_code_from_root test
    result = merge_code_from_root(
        root_dir,
        search_term=None,
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=False,
    )

    # Check that all required sections are present
    assert "----- FOLDER TREE -----" in result
    assert "----- FILE TREE -----" in result
    assert "----- MERGED CODE -----" in result

    # Check the folder tree section
    folder_section = parse_section(result, "----- FOLDER TREE -----")
    assert "subdir" in folder_section
    assert "" not in folder_section  # Make sure there are no empty entries

    # Check the file tree section
    file_section = parse_section(result, "----- FILE TREE -----")

    # Check that files are included
    assert "file1.txt" in file_section
    assert "file2.txt" in file_section
    assert "subdir/file3.txt" in file_section
    assert "subdir/file4.txt" in file_section

    # Check that ignored files are not included
    assert "ignore_me.txt" not in file_section
    assert "exclude_this.log" not in file_section
    assert "subdir/ignore_sub.txt" not in file_section

    # Binary files should be included in the file listing
    assert "binary.bin" in file_section


def test_merge_code_with_search_term(fs, monkeypatch):
    """Test merging code with a search term."""
    root_dir = "/project"
    search_term = "SearchTerm"

    # We need to fix mmap operations since they don't work directly with pyfakefs
    import mmap

    def mock_mmap(*args, **kwargs):
        """
        This mock is necessary because mmap doesn't work with pyfakefs file descriptors
        It just forces file_contains to use the fallback code path
        """
        raise OSError("Mock mmap doesn't work with pyfakefs")

    # Temporarily replace mmap.mmap to force fallback to regular file reading
    monkeypatch.setattr(mmap, "mmap", mock_mmap)

    # Test with string search term (legacy mode)
    result = merge_code_from_root(
        root_dir,
        search_term=search_term,
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=True,
    )

    # Check that only files containing the search term are included
    folder_section = parse_section(result, "----- FOLDER TREE -----")
    assert "subdir" in folder_section

    file_section = parse_section(result, "----- FILE TREE -----")
    assert "file2.txt" in file_section
    assert "subdir/file3.txt" in file_section
    assert "file1.txt" not in file_section  # This file doesn't have the search term

    # Verify line numbers
    assert re.search(r"0001:", result) is not None


def test_merge_code_with_search_config(fs, monkeypatch):
    """Test merging code with a FileContentsSearchConfig object."""
    root_dir = "/project2"

    # Setup test files with content that matches the search patterns
    # Create a directory structure
    fs.create_dir("/project2")
    fs.create_dir("/project2/subdir")

    # Create files with content that includes the patterns
    fs.create_file("/project2/file1.txt", contents="line1\nline2\nThis contains the word file1")
    fs.create_file("/project2/file2.txt", contents="This file contains SearchTerm to find")
    fs.create_file("/project2/subdir/file3.txt", contents="Another file with SearchTerm content")
    fs.create_file("/project2/subdir/file4.txt", contents="No match in this file")

    # Create test files for the ignore patterns
    fs.create_file("/project2/.gitignore", contents="ignore_me.txt\nsubdir/ignore_sub.txt\n")
    fs.create_file("/project2/.aiexclude", contents="exclude_this.log\n")
    fs.create_file("/project2/binary.bin", contents=b"\x00\x01\x02\x03")

    # Create a FileContentsSearchConfig with multiple search criteria
    search_config = FileContentsSearchConfig(
        contains=["SearchTerm"],  # This will match file2.txt and subdir/file3.txt
        regex=[
            re.compile(r"file\d")
        ],  # This will match any file content containing "file1", "file2", etc.
    )

    # We need to fix mmap operations since they don't work directly with pyfakefs
    import mmap

    def mock_mmap(*args, **kwargs):
        """
        This mock is necessary because mmap doesn't work with pyfakefs file descriptors
        It just forces file_contains to use the fallback code path
        """
        raise OSError("Mock mmap doesn't work with pyfakefs")

    # Temporarily replace mmap.mmap to force fallback to regular file reading
    monkeypatch.setattr(mmap, "mmap", mock_mmap)

    result = merge_code_from_root(
        root_dir,
        search_term=search_config,  # Pass the FileContentsSearchConfig object
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=True,
    )

    # Check that files matching the criteria in their content are included
    folder_section = parse_section(result, "----- FOLDER TREE -----")
    assert "subdir" in folder_section

    file_section = parse_section(result, "----- FILE TREE -----")
    # These files should be included because they match the patterns in their content:
    # - file1.txt matches regex "file\d" with content containing "file1"
    # - file2.txt matches "SearchTerm" in content and regex "file\d" with content containing "file2"
    # - subdir/file3.txt matches "SearchTerm" in content
    assert "file1.txt" in file_section
    assert "file2.txt" in file_section
    assert "subdir/file3.txt" in file_section


def test_merge_code_from_root_without_folder_tree(fs):
    """Test merging code from root directory without including the folder tree."""
    root_dir = "/project"

    result = merge_code_from_root(
        root_dir,
        search_term=None,
        include_file_tree=True,
        include_folder_tree=False,  # Explicitly not including folder tree
        include_line_numbers=False,
    )

    # Check that folder tree is not present
    assert "----- FOLDER TREE -----" not in result
    # Check other sections are present
    assert "----- FILE TREE -----" in result
    assert "----- MERGED CODE -----" in result


def test_binary_file_handling(fs):
    """Test that binary files are properly detected and handled."""
    from app.src.codetools import codetools

    # Verify that our binary file is detected as binary
    assert codetools.is_binary_file("/project/binary.bin")

    # Verify that our text files are detected as text
    assert not codetools.is_binary_file("/project/file1.txt")
    assert not codetools.is_binary_file("/project/file2.txt")
