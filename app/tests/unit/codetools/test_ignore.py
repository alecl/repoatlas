import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from app.src.codetools.ignore import IgnorePatternManager

# test_ignore.py to confirm these are effectively covered:

# 1. Patterns without slashes match files and directories in any directory.
# 2. Leading slash (/) matches paths relative to the .gitignore file location.
# 3. Trailing slash (/) matches only directories.
# 4. matches zero or more directories:
#    • //foo matches foo anywhere in the repository.
#    • abc/ matches everything inside abc directory.
#    • a//b matches a/b, a/x/b, a/x/y/b, etc.
#    • matches any characters except /, ? matches any single character except /.
# 5. 0-9 matches a single character in the specified range.
# 6. ! negates a pattern, re-including previously excluded files.
# 7. Patterns in deeper .gitignore files override higher-level ones.
# 8. Blank lines are ignored and can be used for readability.
# 9. Comments start with # and are ignored.


@pytest.fixture
def fs():
    """Setup a fake filesystem with pyfakefs for testing."""
    with Patcher() as patcher:
        # Project structure with multiple levels of .gitignore and .aiexclude
        patcher.fs.create_dir("/project")
        patcher.fs.create_file("/project/.gitignore", contents="root_ignore.log\n")
        patcher.fs.create_file("/project/.aiexclude", contents="root_aiexclude.txt\n")

        patcher.fs.create_dir("/project/subdir")
        patcher.fs.create_file("/project/subdir/.gitignore", contents="subdir_ignore.pyc\n")
        patcher.fs.create_file("/project/subdir/.aiexclude", contents="subdir_aiexclude.tmp\n")

        patcher.fs.create_dir("/project/subdir/nested")
        patcher.fs.create_file("/project/subdir/nested/.gitignore", contents="nested_ignore/\n")

        # Repository with .git (should stop at this level)
        patcher.fs.create_dir("/repo")
        patcher.fs.create_dir("/repo/.git")  # This directory should stop traversal
        patcher.fs.create_file("/repo/.gitignore", contents="*.log\n")

        patcher.fs.create_dir("/repo/sub")
        patcher.fs.create_file("/repo/sub/.gitignore", contents="ignoreme.pyc\n")

        patcher.fs.create_dir("/repo/sub/nested")
        patcher.fs.create_file("/repo/sub/nested/.gitignore", contents="ignoredir/\n")

        # Test files to check ignore patterns
        patcher.fs.create_file("/project/subdir/subdir_ignore.pyc", contents="test content")
        patcher.fs.create_file("/project/subdir/good.py", contents="test content")
        patcher.fs.create_file("/repo/sub/nested/app.log", contents="test content")
        patcher.fs.create_file("/repo/sub/nested/good.py", contents="test content")
        patcher.fs.create_file("/repo/sub/ignoreme.pyc", contents="test content")

        patcher.fs.create_dir("/repo/sub/nested/ignoredir")
        patcher.fs.create_file("/repo/sub/nested/ignoredir/some.txt", contents="test content")

        yield patcher.fs


def test_effective_ignore_single_dir(fs):
    manager = IgnorePatternManager("/project/subdir")
    expected = [
        "root_ignore.log",
        "root_aiexclude.txt",
        "subdir_ignore.pyc",
        "subdir_aiexclude.tmp",
        ".git",
        "venv",
        ".venv",
    ]
    assert manager.patterns == expected


def test_effective_ignore_nested(fs):
    manager = IgnorePatternManager("/project/subdir/nested")
    expected = [
        "root_ignore.log",
        "root_aiexclude.txt",
        "subdir_ignore.pyc",
        "subdir_aiexclude.tmp",
        "nested_ignore/",
        ".git",
        "venv",
        ".venv",
    ]
    assert manager.patterns == expected


def test_effective_ignore_stop_at_git(fs):
    manager = IgnorePatternManager("/repo/sub/nested")
    expected = ["*.log", "ignoreme.pyc", "ignoredir/", ".git", "venv", ".venv"]
    assert manager.patterns == expected


def test_ignore_pattern_manager_reuse(fs):
    """Test that IgnorePatternManager instances reuse calculated patterns."""
    manager = IgnorePatternManager("/project/subdir")
    patterns1 = manager.patterns
    patterns2 = manager.patterns
    assert patterns1 is patterns2  # Same instance


def test_should_ignore_explicit(fs):
    manager = IgnorePatternManager("/project/subdir")
    assert manager.should_ignore("/project/subdir/subdir_ignore.pyc")
    assert not manager.should_ignore("/project/subdir/good.py")


def test_should_ignore_automatic(fs):
    repo_nested_manager = IgnorePatternManager("/repo/sub/nested")
    repo_sub_manager = IgnorePatternManager("/repo/sub")

    assert repo_nested_manager.should_ignore("/repo/sub/nested/app.log")
    assert repo_sub_manager.should_ignore("/repo/sub/ignoreme.pyc")
    assert repo_nested_manager.should_ignore("/repo/sub/nested/ignoredir/some.txt")
    assert not repo_nested_manager.should_ignore("/repo/sub/nested/good.py")


def test_should_ignore_pattern_types(fs):
    fs.create_dir("/patterns")
    fs.create_file(
        "/patterns/.gitignore",
        contents="*.pyc\n__pycache__/\n*.log\n!important.log\ntemp*\nbuild/\n**/secret\n",
    )
    fs.create_file("/patterns/file.pyc", contents="content")
    fs.create_file("/patterns/file.py", contents="content")

    fs.create_dir("/patterns/__pycache__")
    fs.create_file("/patterns/__pycache__/module.cpython-39.pyc", contents="content")

    fs.create_file("/patterns/regular.log", contents="content")
    fs.create_file("/patterns/important.log", contents="content")
    fs.create_file("/patterns/temp", contents="content")
    fs.create_file("/patterns/tempfile.txt", contents="content")

    fs.create_dir("/patterns/build")
    fs.create_file("/patterns/build/output.js", contents="content")

    fs.create_file("/patterns/secret", contents="content")
    fs.create_dir("/patterns/subfolder")
    fs.create_file("/patterns/subfolder/secret", contents="content")
    fs.create_file("/patterns/subfolder/not-secret", contents="content")

    manager = IgnorePatternManager("/patterns")

    assert manager.should_ignore("/patterns/file.pyc")
    assert not manager.should_ignore("/patterns/file.py")
    assert manager.should_ignore("/patterns/__pycache__")
    assert manager.should_ignore("/patterns/__pycache__/module.cpython-39.pyc")
    assert manager.should_ignore("/patterns/regular.log")
    assert not manager.should_ignore("/patterns/important.log")
    assert manager.should_ignore("/patterns/temp")
    assert manager.should_ignore("/patterns/tempfile.txt")
    assert manager.should_ignore("/patterns/build")
    assert manager.should_ignore("/patterns/build/output.js")
    assert manager.should_ignore("/patterns/secret")
    assert manager.should_ignore("/patterns/subfolder/secret")
    assert not manager.should_ignore("/patterns/subfolder/not-secret")


def test_should_ignore_trailing_slash(fs):
    fs.create_dir("/test")
    fs.create_file("/test/.gitignore", contents="logs/\n")
    fs.create_dir("/test/logs")
    fs.create_file("/test/logs/file.log", contents="content")

    manager = IgnorePatternManager("/test")

    assert manager.should_ignore("/test/logs")
    assert manager.should_ignore("/test/logs/")
    assert manager.should_ignore("/test/logs/file.log")


def test_should_ignore_double_star(fs):
    fs.create_dir("/test")
    fs.create_file("/test/.gitignore", contents="**/secret\n")
    fs.create_dir("/test/subfolder")
    fs.create_file("/test/subfolder/secret", contents="content")
    fs.create_file("/test/secret", contents="content")
    fs.create_file("/test/subfolder/public", contents="content")

    manager = IgnorePatternManager("/test")

    assert manager.should_ignore("/test/subfolder/secret")
    assert manager.should_ignore("/test/secret")
    assert not manager.should_ignore("/test/subfolder/public")


def test_should_ignore_complex_patterns(fs):
    fs.create_dir("/test")
    fs.create_file("/test/.gitignore", contents="*.log\n!important.log\ntemp*\nbuild/\n")
    fs.create_file("/test/app.log", contents="content")
    fs.create_file("/test/important.log", contents="content")
    fs.create_file("/test/tempfile.txt", contents="content")
    fs.create_file("/test/temp123", contents="content")

    fs.create_dir("/test/build")
    fs.create_file("/test/build/file.js", contents="content")

    fs.create_dir("/test/src")
    fs.create_file("/test/src/main.py", contents="content")

    manager = IgnorePatternManager("/test")

    assert manager.should_ignore("/test/app.log")
    assert not manager.should_ignore("/test/important.log")
    assert manager.should_ignore("/test/tempfile.txt")
    assert manager.should_ignore("/test/temp123")
    assert manager.should_ignore("/test/build")
    assert manager.should_ignore("/test/build/file.js")
    assert not manager.should_ignore("/test/src/main.py")


def test_leading_slash_behavior(fs):
    """
    Test that a pattern with a leading slash only matches files in the same directory
    as the .gitignore, and not files in subdirectories.
    """
    fs.create_dir("/lead")
    fs.create_file("/lead/.gitignore", contents="/foo.txt\n")
    fs.create_file("/lead/foo.txt", contents="ignored")
    fs.create_dir("/lead/sub")
    fs.create_file("/lead/sub/foo.txt", contents="not ignored")

    manager = IgnorePatternManager("/lead")
    assert manager.should_ignore("/lead/foo.txt")
    assert not manager.should_ignore("/lead/sub/foo.txt")


def test_zero_or_more_directories(fs):
    """
    Test that a pattern with a double slash (e.g., "a//b") matches files with zero or more directories between.
    """
    fs.create_dir("/zero")
    fs.create_file("/zero/.gitignore", contents="a//b\n")
    fs.create_dir("/zero/a")
    fs.create_file("/zero/a/b", contents="ignored")
    fs.create_dir("/zero/a/x")
    fs.create_file("/zero/a/x/b", contents="ignored")
    fs.create_dir("/zero/a/x/y")
    fs.create_file("/zero/a/x/y/b", contents="ignored")
    fs.create_file("/zero/a/x/y/c", contents="not ignored")

    manager = IgnorePatternManager("/zero")
    assert manager.should_ignore("/zero/a/b")
    assert manager.should_ignore("/zero/a/x/b")
    assert manager.should_ignore("/zero/a/x/y/b")
    assert not manager.should_ignore("/zero/a/x/y/c")


def test_character_range_matching(fs):
    """
    Test that patterns with character ranges only match a single character in the specified range.
    """
    fs.create_dir("/range")
    fs.create_file("/range/.gitignore", contents="file[0-9].txt\n")
    fs.create_file("/range/file1.txt", contents="ignored")
    fs.create_file("/range/file9.txt", contents="ignored")
    fs.create_file("/range/file10.txt", contents="not ignored")
    fs.create_file("/range/filea.txt", contents="not ignored")

    manager = IgnorePatternManager("/range")
    assert manager.should_ignore("/range/file1.txt")
    assert manager.should_ignore("/range/file9.txt")
    assert not manager.should_ignore("/range/file10.txt")
    assert not manager.should_ignore("/range/filea.txt")


def test_blank_lines_and_comments(fs):
    """
    Test that blank lines and comments in .gitignore files are ignored.
    """
    fs.create_dir("/blank")
    contents = """
# This is a comment

foo.txt

# Another comment
bar.txt
"""
    fs.create_file("/blank/.gitignore", contents=contents)

    manager = IgnorePatternManager("/blank")
    expected = ["foo.txt", "bar.txt", ".git", "venv", ".venv"]
    assert manager.patterns == expected
    fs.create_file("/blank/foo.txt", contents="ignored")
    fs.create_file("/blank/bar.txt", contents="ignored")
    fs.create_file("/blank/baz.txt", contents="not ignored")
    assert manager.should_ignore("/blank/foo.txt")
    assert manager.should_ignore("/blank/bar.txt")
    assert not manager.should_ignore("/blank/baz.txt")


def test_additional_ignore_files_and_patterns(fs):
    """Test that IgnorePatternManager correctly handles additional files and patterns."""
    fs.create_dir("/additional")
    fs.create_file("/additional/.gitignore", contents="*.log\n")
    fs.create_file("/additional/extra_ignore", contents="*.tmp\n")
    fs.create_file("/additional/file.log", contents="content")
    fs.create_file("/additional/file.tmp", contents="content")
    fs.create_file("/additional/file.txt", contents="content")
    fs.create_file("/additional/special.md", contents="content")

    # Create manager with additional ignore files and patterns
    manager = IgnorePatternManager(
        "/additional",
        additional_ignore_files=["extra_ignore"],
        additional_ignore_patterns=["*.md"],
    )

    # Verify all patterns are applied
    assert manager.should_ignore("/additional/file.log")  # From .gitignore
    assert manager.should_ignore("/additional/file.tmp")  # From extra_ignore
    assert manager.should_ignore("/additional/special.md")  # From additional patterns
    assert not manager.should_ignore("/additional/file.txt")  # Not ignored
