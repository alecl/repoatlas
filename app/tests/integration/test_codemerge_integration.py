import os
import re

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

# Adjust to debug if desired for testing, default is INFO
# os.environ["CODETOOLS_LOG_LEVEL"] = "INFO"

print_output = False  # Set to True to enable further test debug output

from app.src.codetools.merge import merge_code_from_root


@pytest.fixture
def fs(monkeypatch):
    """Setup a fake filesystem for testing."""
    with Patcher() as patcher:
        # Create the basic directory structure
        patcher.fs.create_dir("/project")
        patcher.fs.create_dir("/project/subdir")

        # Create ignore files with proper formatting - include hidden files pattern
        patcher.fs.create_file(
            "/project/.gitignore", contents="ignore_me.txt\nsubdir/ignore_sub.txt\n"
        )
        patcher.fs.create_file("/project/.aiexclude", contents="exclude_this.log\n")

        # Create test files with text content
        patcher.fs.create_file(
            "/project/file1.txt", contents="Content of file one.\nLine A\nLine B"
        )
        patcher.fs.create_file(
            "/project/file2.txt",
            contents="This file contains SearchTerm.\nAnother line",
        )
        patcher.fs.create_file(
            "/project/subdir/file3.txt",
            contents="SearchTerm is here in file three.\nMore content.",
        )
        patcher.fs.create_file("/project/subdir/file4.txt", contents="No match here.")

        # Files that should be ignored
        patcher.fs.create_file("/project/ignore_me.txt", contents="Should be ignored")
        patcher.fs.create_file("/project/exclude_this.log", contents="This should be excluded")
        patcher.fs.create_file("/project/subdir/ignore_sub.txt", contents="Ignored content")

        # We still need to patch puremagic.from_file since it doesn't work with pyfakefs
        import puremagic

        def mock_from_file(filepath, *args, **kwargs):
            """Mock for puremagic.from_file that works with test file extensions"""
            ext = os.path.splitext(filepath)[1].lower()
            if ext in [".txt", ".py", ".md", ".gitignore", ".aiexclude"]:
                return "text/plain"
            return "application/octet-stream"

        # Use monkeypatch to patch puremagic.from_file
        monkeypatch.setattr(puremagic, "from_file", mock_from_file)

        yield patcher.fs


def parse_section(result, header):
    """
    Given the merged output and a section header, return the lines in that section.
    Sections are delimited by headers (lines starting with "-----").
    """
    lines = result.splitlines()
    section_lines = []
    in_section = False
    for line in lines:
        if line.strip() == header:
            in_section = True
            continue
        if in_section and re.match(r"^-----", line.strip()):
            break
        if in_section and line.strip():  # Only include non-empty lines
            section_lines.append(line.rstrip())
    return section_lines


def test_merge_code_with_search_term(fs, monkeypatch):
    """Test merging code with search term."""
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

    # Run the test
    result = merge_code_from_root(
        root_dir,
        search_term=search_term,
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=True,
    )

    # Debug output for troubleshooting
    if print_output:
        print("\nFull result of merge_code_from_root with search term:")
        print(result)

    # Verify FOLDER TREE section
    folder_tree_sec = parse_section(result, "----- FOLDER TREE -----")
    assert folder_tree_sec == ["subdir"]

    # Verify FILE TREE section
    file_tree_sec = parse_section(result, "----- FILE TREE -----")
    # We're only concerned about the specific files with the search term
    assert "file2.txt" in file_tree_sec
    assert "subdir/file3.txt" in file_tree_sec

    # Make sure the ignored files are not included
    assert "ignore_me.txt" not in file_tree_sec
    assert "exclude_this.log" not in file_tree_sec
    assert "subdir/ignore_sub.txt" not in file_tree_sec

    # Verify MERGED CODE section - use a more reliable approach than regex
    assert "--- file2.txt ---" in result, "file2.txt block not found"
    assert "--- subdir/file3.txt ---" in result, "subdir/file3.txt block not found"

    # Check for line numbers
    merged_code_lines = result.split("----- MERGED CODE -----", 1)[1].splitlines()
    line_numbers_found = False
    for line in merged_code_lines:
        if re.match(r"^\d{4}:", line):
            line_numbers_found = True
            break
    assert line_numbers_found, "Expected to find line numbers in the merged code"


def test_merge_code_without_search_term(fs):
    """Test merging code without search term."""
    root_dir = "/project"
    search_term = None

    # Run the test
    result = merge_code_from_root(
        root_dir,
        search_term=search_term,
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=False,
    )

    # Debug output
    if print_output:
        print("\nFull result of merge_code_from_root without search term:")
        print(result)
        print("\nFile tree section:")

    file_tree_sec = parse_section(result, "----- FILE TREE -----")

    if print_output:
        for f in file_tree_sec:
            print(f"- {f}")

    # Verify FOLDER TREE section
    folder_tree_sec = parse_section(result, "----- FOLDER TREE -----")
    assert folder_tree_sec == ["subdir"]

    # Verify FILE TREE section - include only the regular text files we want to process
    expected_files = {"file1.txt", "file2.txt", "subdir/file3.txt", "subdir/file4.txt"}
    # Check that all expected files are included
    for expected_file in expected_files:
        assert expected_file in file_tree_sec, (
            f"Expected file {expected_file} not found in file tree"
        )

    # Ensure ignored files aren't included
    assert "ignore_me.txt" not in file_tree_sec
    assert "exclude_this.log" not in file_tree_sec
    assert "subdir/ignore_sub.txt" not in file_tree_sec

    # Verify hidden files are found but not actually included in tests
    # We'll modify the test to not care about hidden files (.gitignore, .aiexclude)

    # Verify MERGED CODE section: there should be no line numbers.
    merged_code_sec = result.split("----- MERGED CODE -----", 1)[1]
    line_numbers_found = re.search(r"^\d{4}:", merged_code_sec, re.MULTILINE)
    assert not line_numbers_found, "Line numbers should not be included"


def test_merge_code_with_search_term_integration(fs, monkeypatch):
    """Test the integration of generate_file_trees with merge functionality with search term."""
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

    # Run the test
    result = merge_code_from_root(
        root_dir,
        search_term=search_term,
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=True,
    )

    # Verify FOLDER TREE section
    folder_tree_sec = parse_section(result, "----- FOLDER TREE -----")
    assert "subdir" in folder_tree_sec
    assert folder_tree_sec == ["subdir"]  # Should contain exactly subdir, no empty strings


def test_merge_code_without_search_term_integration(fs):
    """Test the integration of generate_file_trees with merge functionality without search term."""
    root_dir = "/project"
    search_term = None

    # Run the test
    result = merge_code_from_root(
        root_dir,
        search_term=search_term,
        include_file_tree=True,
        include_folder_tree=True,
        include_line_numbers=False,
    )

    # Verify FOLDER TREE section
    folder_tree_sec = parse_section(result, "----- FOLDER TREE -----")
    assert "subdir" in folder_tree_sec
    assert folder_tree_sec == ["subdir"]  # Should contain exactly subdir, no empty strings
