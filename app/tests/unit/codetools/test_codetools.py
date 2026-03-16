import re

from app.src.codetools.codetools import (
    FileContentsSearchConfig,
    file_contains,
    generate_file_trees,
    merge_file_trees,
)
from app.src.codetools.ignore import IgnorePatternManager

# -------------------------------
# Tests for file_contains
# -------------------------------


def test_file_contains_small_file(mocker):
    mocker.patch("os.path.getsize", return_value=10)
    # Use mocker.mock_open to return bytes data.
    mocked_open = mocker.mock_open(read_data=b"hello world")
    mocker.patch("builtins.open", mocked_open)
    # Test with string (legacy mode)
    assert file_contains("/fake/file.txt", "world")
    # Test with SearchConfig
    assert file_contains("/fake/file.txt", FileContentsSearchConfig(contains=["world"]))


def test_file_contains_large_file(mocker):
    mocker.patch("os.path.getsize", return_value=10_000_000)
    # Use mocker.mock_open to return bytes data.
    mocked_open = mocker.mock_open(read_data=b"hello world")
    mocker.patch("builtins.open", mocked_open)
    # Simulate mmap throwing OSError for large files.
    mocker.patch("mmap.mmap", side_effect=OSError)
    # Test with string (legacy mode)
    assert not file_contains("/fake/file.txt", "not in file")
    # Test with SearchConfig
    assert not file_contains("/fake/file.txt", FileContentsSearchConfig(contains=["not in file"]))


def test_file_contains_empty_file(mocker):
    # Simulate an empty file (size 0)
    mocker.patch("os.path.getsize", return_value=0)
    mocked_open = mocker.mock_open(read_data=b"")
    mocker.patch("builtins.open", mocked_open)
    assert not file_contains("/fake/file.txt", "anything")
    assert not file_contains("/fake/file.txt", FileContentsSearchConfig(contains=["anything"]))


def test_file_contains_exception_reading(mocker):
    # Simulate an exception during reading a small file.
    mocker.patch("os.path.getsize", return_value=10)
    mocker.patch("builtins.open", side_effect=IOError)
    # Assuming the function catches the exception and returns False.
    assert not file_contains("/fake/file.txt", "anything")
    assert not file_contains("/fake/file.txt", FileContentsSearchConfig(contains=["anything"]))


def test_file_contains_with_regex(mocker):
    mocker.patch("os.path.getsize", return_value=100)
    mocked_open = mocker.mock_open(read_data=b"hello world 123")
    mocker.patch("builtins.open", mocked_open)

    # Test with regex pattern
    search_config = FileContentsSearchConfig(regex=[re.compile(r"\d+")])
    assert file_contains("/fake/file.txt", search_config)

    # Test with non-matching regex
    search_config = FileContentsSearchConfig(regex=[re.compile(r"xyz\d+")])
    assert not file_contains("/fake/file.txt", search_config)


def test_file_contains_with_file_type_map(mocker):
    mocker.patch("os.path.getsize", return_value=100)
    mocked_open = mocker.mock_open(read_data="function test() { return 42; }")
    mocker.patch("builtins.open", mocked_open)

    # Test with file_type_map for .js files
    search_config = FileContentsSearchConfig(
        file_type_map={".js": re.compile(r"function\s+\w+\s*\(\)")}
    )
    assert file_contains("/fake/file.js", search_config)

    # Test with non-matching extension
    assert not file_contains("/fake/file.txt", search_config)


def test_file_contains_with_multiple_criteria(fs):
    """Test complex content matching with multiple criteria and file types.

    Note: FileContentsSearchConfig only matches file contents, not filenames.
    """
    # Create test files with different content types
    fs.create_file(
        "/test/react.jsx",
        contents="""
        import React from 'react';
        import { useState } from 'react';

        export function Component() {
            const [state, setState] = useState(null);
            return <div>Test</div>;
        }
        """,
    )

    fs.create_file(
        "/test/utils.ts",
        contents="""
        export function parseData(input: string): Record<string, any> {
            return JSON.parse(input);
        }

        // TODO: Add error handling
        export async function fetchData() {
            const response = await fetch('/api/data');
            return response.json();
        }
        """,
    )

    fs.create_file(
        "/test/styles.css",
        contents="""
        .component {
            display: flex;
            background-color: #fff;
        }

        .button {
            padding: 8px 16px;
            border-radius: 4px;
        }
        """,
    )

    # Test multiple criteria matching - all criteria types have OR logic between them
    config1 = FileContentsSearchConfig(
        contains=["React", "useState"],
        regex=[re.compile(r"import\s+.*\s+from\s+'react'")],
        file_type_map={".jsx": re.compile(r"<.*>.*</.*>")},
    )
    assert file_contains("/test/react.jsx", config1)
    # utils.ts doesn't match any criteria in config1
    assert not file_contains("/test/utils.ts", config1)

    # Test TypeScript-specific patterns
    config2 = FileContentsSearchConfig(
        contains=["export"],
        regex=[re.compile(r":\s*[A-Za-z<>]+")],
        file_type_map={".ts": re.compile(r"async\s+function")},
    )
    assert file_contains("/test/utils.ts", config2)
    # react.jsx should match the "export" in contains criteria, so it should return True
    assert file_contains("/test/react.jsx", config2)

    # Test CSS patterns
    config3 = FileContentsSearchConfig(
        regex=[re.compile(r"\{[^}]*display:\s*flex[^}]*\}")],
        file_type_map={".css": re.compile(r"\.[\w-]+\s*\{")},
    )
    assert file_contains("/test/styles.css", config3)
    # utils.ts doesn't match any criteria in config3
    assert not file_contains("/test/utils.ts", config3)


# -------------------------------
# Tests for generate_file_trees
# -------------------------------


def test_generate_file_trees(fs, mocker):
    """Test file tree generation with actual content matching.

    Note: FileContentsSearchConfig only matches file contents, not filenames.
    """
    # Setup test files with specific content
    fs.create_dir("/fake/dir")
    fs.create_dir("/fake/dir/subdir")
    # Content that includes both the search term and text resembling the filename pattern
    fs.create_file("/fake/dir/file1.txt", contents="This is file1\nText with file1.txt pattern")
    fs.create_file("/fake/dir/file2.txt", contents="This file contains SearchTerm")
    fs.create_file("/fake/dir/subdir/file3.txt", contents="Another SearchTerm match")
    fs.create_file("/fake/dir/subdir/file4.txt", contents="No match in this file")
    fs.create_file("/fake/dir/file5.bin", contents=b"\x00\x01\x02\x03")

    # Patch the _calculate_patterns method to return our test patterns
    # This allows the real should_ignore logic to run with our test patterns
    mocker.patch(
        "app.src.codetools.ignore.IgnorePatternManager._calculate_patterns",
        return_value=["*.bin"],
    )

    # Test with string search (legacy mode)
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir", "SearchTerm"
    )
    assert set(all_files) == {
        "file1.txt",
        "file2.txt",
        "subdir/file3.txt",
        "subdir/file4.txt",
    }
    assert set(all_folders) == {"subdir"}
    assert set(matching_files) == {"file2.txt", "subdir/file3.txt"}
    assert set(matching_folders) == {"subdir"}

    # Test with FileContentsSearchConfig containing multiple criteria - files match if ANY criteria matches
    config = FileContentsSearchConfig(
        contains=["SearchTerm"],
        regex=[re.compile(r"file[1-3]\.txt")],
    )
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir", config
    )

    # Files matching ANY criteria in their contents should be included:
    # - file1.txt has "file1.txt" in its content, matching the regex r"file[1-3]\.txt"
    # - file2.txt has "SearchTerm" in content
    # - subdir/file3.txt has "SearchTerm" in content
    expected_matching = {"file1.txt", "file2.txt", "subdir/file3.txt"}
    assert set(matching_files) == expected_matching


def test_merge_file_trees(mocker):
    """Test merging additional files into existing file trees."""
    # Initial file trees
    all_files = ["file1.txt", "dir1/file2.txt"]
    all_folders = ["dir1"]
    matching_files = ["dir1/file2.txt"]
    matching_folders = ["dir1"]

    # Files to add
    files_to_add = [
        "dir1/file3.txt",
        "dir2/file4.txt",
        "file1.txt",
    ]  # Note: file1.txt is duplicate

    # Merge the trees
    new_all_files, new_all_folders, new_matching_files, new_matching_folders = merge_file_trees(
        files_to_add, all_files, all_folders, matching_files, matching_folders
    )

    # Verify results
    assert set(new_all_files) == {
        "file1.txt",
        "dir1/file2.txt",
        "dir1/file3.txt",
        "dir2/file4.txt",
    }
    assert set(new_all_folders) == {"dir1", "dir2"}
    assert set(new_matching_files) == {"dir1/file2.txt"}  # Unchanged
    assert set(new_matching_folders) == {"dir1"}  # Unchanged


def test_generate_file_trees_with_additional_ignores(fs, mocker):
    """Test generate_file_trees with additional ignore patterns and files."""
    # Create a directory structure with files
    fs.create_dir("/fake/dir")
    fs.create_dir("/fake/dir/subdir")

    # Create files with appropriate content
    fs.create_file("/fake/dir/file1.txt", contents="This is file1")
    fs.create_file("/fake/dir/file2.txt", contents="This file contains specific content to match")
    fs.create_file("/fake/dir/ignore.txt", contents="This file should be ignored")
    fs.create_file("/fake/dir/document.pdf", contents="PDF content")
    fs.create_file("/fake/dir/document.md", contents="Markdown document")
    fs.create_file("/fake/dir/data.json", contents='{"key": "value"}')
    fs.create_file("/fake/dir/subdir/file3.txt", contents="Subdir file")
    fs.create_file("/fake/dir/subdir/temp.tmp", contents="Temporary file")

    # Create a custom ignore file with patterns
    fs.create_file("/fake/dir/custom_ignore", contents="# Custom ignore patterns\n*.pdf")

    # Create an existing .gitignore and .aiexclude
    fs.create_file("/fake/dir/.gitignore", contents="# Git ignore patterns\n*.md")
    fs.create_file("/fake/dir/.aiexclude", contents="# AI exclude patterns\n*.json")

    # Instead of mocking _calculate_patterns, we'll spy on the IgnorePatternManager's method calls
    # to ensure it's being created with the right parameters
    # This lets the real logic execute while we monitor the calls
    _ = mocker.spy(IgnorePatternManager, "__init__")  # Spy on init but result not needed

    # First test: Just use the standard patterns from .gitignore and .aiexclude
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir",
        FileContentsSearchConfig(contains=["specific content"]),
        # No additional patterns or files
    )

    # Verify baseline behavior - .md and .json files should be ignored
    # These come from the .gitignore and .aiexclude files
    assert "file1.txt" in all_files, "Text file should be included"
    assert "file2.txt" in all_files, "Text file should be included"
    assert "document.pdf" in all_files, "PDF file should be included"
    assert "document.md" not in all_files, "MD file should be ignored (.gitignore)"
    assert "data.json" not in all_files, "JSON file should be ignored (.aiexclude)"
    assert "file2.txt" in matching_files, "File with matching content should be in matching_files"

    # Second test: Use the custom_ignore file
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir",
        FileContentsSearchConfig(contains=["specific content"]),
        additional_ignore_files=["custom_ignore"],  # Should pick up *.pdf pattern
    )

    # Now PDF should also be ignored along with MD and JSON
    assert "file1.txt" in all_files, "Text file should still be included"
    assert "document.pdf" not in all_files, "PDF file should be ignored by custom_ignore"
    assert "document.md" not in all_files, "MD file should still be ignored"
    assert "data.json" not in all_files, "JSON file should still be ignored"

    # Third test: Use additional_ignore_patterns directly
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir",
        FileContentsSearchConfig(contains=["specific content"]),
        additional_ignore_patterns=[
            "*.txt",
            "*.tmp",
        ],  # Ignore all text files and temp files
    )

    # Now txt files should also be ignored
    assert "file1.txt" not in all_files, "TXT file should be ignored"
    assert "file2.txt" not in all_files, "TXT file should be ignored"
    assert "subdir/file3.txt" not in all_files, "TXT file should be ignored"
    assert "subdir/temp.tmp" not in all_files, "TMP file should be ignored"
    assert "document.pdf" in all_files, "PDF file should be included"
    assert len(matching_files) == 0, "No files should match since text files are ignored"

    # Verify that 'subdir' is not in all_folders since all its files are ignored
    assert "subdir" not in all_folders, (
        "Directory with all files ignored should not be in all_folders"
    )


def test_generate_file_trees_empty_directory(mocker):
    # Test when os.walk returns an empty list.
    mocker.patch("os.walk", return_value=[])

    # Patch _calculate_patterns to return an empty list
    mocker.patch(
        "app.src.codetools.ignore.IgnorePatternManager._calculate_patterns",
        return_value=[],
    )

    # Test with string (legacy mode)
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/empty", "search"
    )
    assert all_files == []
    assert all_folders == []
    assert matching_files == []
    assert matching_folders == []

    # Test with SearchConfig
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/empty", FileContentsSearchConfig(contains=["search"])
    )
    assert all_files == []
    assert all_folders == []
    assert matching_files == []
    assert matching_folders == []


def test_generate_file_trees_nested_files(fs, mocker):
    """Test file tree generation with deeply nested structure and various content types.

    Note: FileContentsSearchConfig only matches file contents, not filenames.
    """
    # Create a complex nested directory structure
    fs.create_dir("/project")
    fs.create_dir("/project/src")
    fs.create_dir("/project/src/components")
    fs.create_dir("/project/src/utils")
    fs.create_dir("/project/tests")
    fs.create_dir("/project/tests/unit")
    fs.create_dir("/project/docs")

    # Create files with specific content patterns
    fs.create_file(
        "/project/src/index.ts",
        contents="""
        import { App } from './components/App';
        export default App;
    """,
    )

    fs.create_file(
        "/project/src/components/App.tsx",
        contents="""
        import React from 'react';
        import { Header } from './Header';
        import { useAuth } from '../utils/auth';

        export function App() {
            const { user } = useAuth();
            return (
                <div className="app">
                    <Header user={user} />
                    <main>Content</main>
                </div>
            );
        }
    """,
    )

    fs.create_file(
        "/project/src/utils/auth.ts",
        contents="""
        export interface User {
            id: string;
            name: string;
        }

        export function useAuth() {
            // TODO: Implement authentication
            return { user: null };
        }
    """,
    )

    fs.create_file(
        "/project/tests/unit/auth.test.ts",
        contents="""
        import { useAuth } from '../../src/utils/auth';

        describe('useAuth', () => {
            it('should return null user by default', () => {
                const { user } = useAuth();
                expect(user).toBeNull();
            });
        });
    """,
    )

    # Mock _calculate_patterns to return patterns that would ignore node_modules and .log files
    mocker.patch(
        "app.src.codetools.ignore.IgnorePatternManager._calculate_patterns",
        return_value=["node_modules/", "*.log"],
    )

    # Test with multiple search criteria
    config = FileContentsSearchConfig(
        contains=["import", "export"],
        regex=[
            re.compile(r"interface\s+\w+\s*\{"),
            re.compile(r"function\s+\w+\s*\([^)]*\)"),
        ],
        file_type_map={
            ".tsx": re.compile(r"<[^>]+>[^<]*</[^>]+>"),
            ".test.ts": re.compile(r"describe\(.*it\("),
        },
    )

    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/project", config
    )

    # Verify file structure
    assert set(all_files) == {
        "src/index.ts",
        "src/components/App.tsx",
        "src/utils/auth.ts",
        "tests/unit/auth.test.ts",
    }

    # Note we exclude 'docs' since it has no non-ignored files
    assert set(all_folders) == {
        "src",
        "src/components",
        "src/utils",
        "tests",
        "tests/unit",
    }

    # Verify matching files based on content
    # All files have matching content (not filenames):
    # - src/index.ts has "import" and "export"
    # - src/components/App.tsx has "import", "export", "function", and matches TSX pattern
    # - src/utils/auth.ts has "export", "interface", and "function"
    # - tests/unit/auth.test.ts has "import" and matches test pattern
    expected_matching = {
        "src/index.ts",
        "src/components/App.tsx",
        "src/utils/auth.ts",
        "tests/unit/auth.test.ts",
    }
    assert set(matching_files) == expected_matching


def test_generate_file_trees_with_regex_search(fs, mocker):
    """Test file tree generation with regex search, using real file content."""
    # Create directory structure with files containing specific content
    fs.create_dir("/fake/dir")
    # Files with content matching regex pattern
    fs.create_file("/fake/dir/file1.js", contents="This has js code")
    fs.create_file("/fake/dir/file2.py", contents="This has py code")
    # File without matching content
    fs.create_file("/fake/dir/file3.txt", contents="This is just text")

    # Mock _calculate_patterns to return an empty list (no ignored files)
    mocker.patch(
        "app.src.codetools.ignore.IgnorePatternManager._calculate_patterns",
        return_value=[],
    )

    # Test with regex pattern that would match "js" or "py" in file content
    search_config = FileContentsSearchConfig(regex=[re.compile(r"js|py")])
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir", search_config
    )

    assert set(all_files) == {"file1.js", "file2.py", "file3.txt"}
    assert set(matching_files) == {"file1.js", "file2.py"}


def test_generate_file_trees_with_file_type_map(fs, mocker):
    """Test file tree generation with file_type_map, using real file content."""
    # Create directory structure with files containing specific content
    fs.create_dir("/fake/dir")
    # File with JS function that would match the file_type_map pattern
    fs.create_file("/fake/dir/script.js", contents="function doSomething() { return true; }")
    # Files that won't match the pattern
    fs.create_file("/fake/dir/style.css", contents=".class { color: red; }")
    fs.create_file("/fake/dir/document.md", contents="# Markdown Document")

    # Mock _calculate_patterns to return an empty list (no ignored files)
    mocker.patch(
        "app.src.codetools.ignore.IgnorePatternManager._calculate_patterns",
        return_value=[],
    )

    # Test with file_type_map that matches JS files containing "function"
    search_config = FileContentsSearchConfig(file_type_map={".js": re.compile(r"function")})
    all_files, all_folders, matching_files, matching_folders = generate_file_trees(
        "/fake/dir", search_config
    )

    assert set(all_files) == {"document.md", "script.js", "style.css"}
    assert set(matching_files) == {"script.js"}


# -------------------------------
# Tests for is_binary_file
# -------------------------------


def test_is_binary_file_tests(fs, monkeypatch):
    """Consolidated binary file tests using pyfakefs instead of tmp_path."""
    from app.src.codetools.codetools import is_binary_file

    # Test known text file
    fs.create_file("/test/text.txt", contents="hello world")
    assert is_binary_file("/test/text.txt") is False

    # Test known binary extension
    fs.create_file("/test/binary.class", contents="not important content")
    assert is_binary_file("/test/binary.class") is True

    # Test with binary content (null bytes)
    fs.create_file("/test/with_nulls.bin", contents=b"hello\x00world")
    assert is_binary_file("/test/with_nulls.bin") is True

    # Test with UTF-8 BOM
    fs.create_file("/test/utf8_bom.txt", contents=b"\xef\xbb\xbfThis is UTF-8 with BOM")
    assert is_binary_file("/test/utf8_bom.txt") is False

    # Mock puremagic for edge cases
    def fake_text_mime(path, mime=True):
        return "text/plain"

    def fake_binary_mime(path, mime=True):
        return "application/octet-stream"

    def fake_error_mime(path, mime=True):
        raise Exception("Simulated failure")

    # Test with puremagic reporting text/plain
    monkeypatch.setattr(
        "app.src.codetools.codetools.puremagic",
        type("FakePureMagic", (), {"from_file": fake_text_mime}),
    )
    fs.create_file("/test/unknown_text.xyz", contents="text content")
    assert is_binary_file("/test/unknown_text.xyz") is False

    # Test with puremagic reporting binary
    monkeypatch.setattr(
        "app.src.codetools.codetools.puremagic",
        type("FakePureMagic", (), {"from_file": fake_binary_mime}),
    )
    fs.create_file("/test/unknown_binary.xyz", contents="might be binary")
    assert is_binary_file("/test/unknown_binary.xyz") is True

    # Test with puremagic failing and heuristic detecting binary
    monkeypatch.setattr(
        "app.src.codetools.codetools.puremagic",
        type("FakePureMagic", (), {"from_file": fake_error_mime}),
    )
    fs.create_file("/test/heuristic_binary.xyz", contents=b"hello\x00world")
    assert is_binary_file("/test/heuristic_binary.xyz") is True
