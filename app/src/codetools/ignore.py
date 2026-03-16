import fnmatch
import os
from typing import List, Optional

# TODO - add absolute file path ignore patterns and added files too for testing
from .logging import logger


class IgnorePatternManager:
    """
    Class to manage gitignore-style ignore patterns for a directory.
    Encapsulates pattern calculation and directory ignore checks.
    """

    def __init__(
        self,
        start_dir: str,
        additional_ignore_files: list[str] | None = None,
        additional_ignore_patterns: list[str] | None = None,
    ):
        """
        Initialize a new IgnorePatternManager for the given directory.

        Args:
            start_dir (str): The directory to start searching from.
            additional_ignore_files (Optional[List[str]]): Additional files to read for
                ignore patterns.
            additional_ignore_patterns (Optional[List[str]]): Additional patterns to ignore.
        """
        self.base_dir = start_dir
        self.patterns = self._calculate_patterns(
            start_dir, additional_ignore_files, additional_ignore_patterns
        )

    def _read_ignore_file(self, file_path: str) -> list[str]:
        """
        Read ignore patterns from a file, ignoring blank lines and lines starting with '#'.

        Args:
            file_path (str): The path to the ignore file.

        Returns:
            List[str]: A list of ignore patterns from the file.
        """
        patterns = []
        try:
            with open(file_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except Exception:
            pass
        return patterns

    def _calculate_patterns(
        self,
        start_dir: str,
        additional_ignore_files: list[str] | None = None,
        additional_ignore_patterns: list[str] | None = None,
    ) -> list[str]:
        """
        Calculate the effective ignore patterns for a directory by merging any .gitignore
        and .aiexclude files found in that directory and in its parent directories (up to
        5 levels), stopping when a directory containing a '.git' folder is encountered.
        The contents of any found .gitignore and .aiexclude files are merged together.
        Parent directories are processed first (so that their rules have lower precedence)
        and then lower directories override them.

        Args:
            start_dir (str): The directory to start searching from.
            additional_ignore_files (Optional[List[str]]): Additional files to read for ignore patterns.
            additional_ignore_patterns (Optional[List[str]]): Additional patterns to ignore.

        Returns:
            List[str]: A merged list of ignore patterns.
        """
        logger.trace(f"Calculating effective ignore patterns for: {start_dir}")

        # Build directory path hierarchy from start_dir up to root or .git folder
        dirs = []
        current = start_dir

        while True:
            # Add the current directory to our list
            dirs.append(current)

            # Check if the current directory has a .git folder
            if os.path.isdir(os.path.join(current, ".git")):
                break  # Stop when we find a .git folder

            # Get the parent directory
            parent = os.path.dirname(current)

            # Stop if we've reached the root
            if parent == current or parent == "/":
                break

            # Move up to parent
            current = parent

        # Reverse the list so parent directories are processed first
        dirs.reverse()

        # Collect patterns from each directory
        patterns = []
        for d in dirs:
            gitignore_path = os.path.join(d, ".gitignore")
            aiexclude_path = os.path.join(d, ".aiexclude")

            if os.path.exists(gitignore_path):
                patterns.extend(self._read_ignore_file(gitignore_path))

            if os.path.exists(aiexclude_path):
                patterns.extend(self._read_ignore_file(aiexclude_path))

        # Add core ignore patterns
        core_patterns = [".git", "venv", ".venv"]
        patterns.extend(core_patterns)

        # Process additional ignore files
        if additional_ignore_files:
            for file_path in additional_ignore_files:
                # Handle both absolute and relative paths
                if not os.path.isabs(file_path):
                    file_path = os.path.join(start_dir, file_path)

                if os.path.exists(file_path):
                    logger.debug("Loading additional ignore patterns from: %s", file_path)
                    patterns.extend(self._read_ignore_file(file_path))
                else:
                    logger.debug("Additional ignore file not found: %s", file_path)

        # Add additional patterns
        if additional_ignore_patterns:
            logger.debug(f"Adding additional ignore patterns: {additional_ignore_patterns}")
            patterns.extend(additional_ignore_patterns)

        return patterns

    def _match_pattern(self, rel_path: str, pat: str) -> bool:
        """
        Match a relative path against a gitignore-style pattern.
        """
        logger.trace(f"Entering _match_pattern: rel_path='{rel_path}', original pattern='{pat}'")

        # Normalize double slashes to '/**/' if not already present
        if "//" in pat and "**" not in pat:
            pat = pat.replace("//", "/**/")
            logger.trace(f"Normalized pattern with double slash: '{pat}'")

        # Handle patterns with leading slash (anchored to the root)
        if pat.startswith("/"):
            logger.trace("Pattern starts with '/', anchoring to root")
            pat = pat[1:]
            if pat and not pat.endswith("/"):
                pat = pat + "/"
                logger.trace(f"Modified pattern to add trailing '/': '{pat}'")

        # Handle patterns that end with slash (match directories)
        if pat.endswith("/"):
            logger.trace("Pattern ends with '/', matching directories")
            pat = pat.rstrip("/")
            result = rel_path == pat or rel_path.startswith(pat + "/")
            logger.trace(f"Directory match result for pattern '{pat}': {result}")
            return result

        # Efficient special case for the basic **/ pattern
        if pat.startswith("**/") and "/" not in pat[3:]:
            logger.trace("Handling **/ special case")
            sub_pat = pat[3:]
            result = rel_path == sub_pat or rel_path.endswith("/" + sub_pat)
            logger.trace(f"**/ match result for sub-pattern '{sub_pat}': {result}")
            return result

        # Handle complex patterns with '**'
        if "**" in pat:
            logger.trace("Handling complex pattern with **")
            # If pattern contains "/**/", try an alternate candidate without the extra wildcard.
            if "/**/" in pat:
                alt_pat = pat.replace("/**/", "/")
                logger.trace(f"Alternate pattern without '**': '{alt_pat}'")
                if fnmatch.fnmatch(rel_path, alt_pat):
                    logger.trace(f"Match found using alternate pattern '{alt_pat}'")
                    return True
            expanded_pat = pat.replace("**", "*")
            logger.trace(f"Expanded pattern is '{expanded_pat}'")
            if pat.startswith("**") and not fnmatch.fnmatch(rel_path, expanded_pat):
                if expanded_pat.startswith("*/"):
                    alt2_pat = expanded_pat[2:]
                    logger.trace(f"Trying alternative expanded pattern '{alt2_pat}'")
                    if fnmatch.fnmatch(rel_path, alt2_pat):
                        return True
            result = fnmatch.fnmatch(rel_path, expanded_pat)
            logger.trace(f"Complex match result using expanded pattern '{expanded_pat}': {result}")
            return result

        # Handle simple patterns without slashes (match basename only)
        if "/" not in pat:
            result = fnmatch.fnmatch(os.path.basename(rel_path), pat)
            logger.trace(
                f"Simple pattern match against basename: pattern '{pat}', result: {result}"
            )
            return result

        # Default: match against the full path
        result = fnmatch.fnmatch(rel_path, pat)
        logger.trace(f"Default full-path match: pattern '{pat}', result: {result}")
        return result

    def should_ignore(self, path: str) -> bool:
        """
        Determine if a file or directory should be ignored based on .gitignore-style patterns.

        Args:
            path (str): The path to check.

        Returns:
            bool: True if the path should be ignored, False otherwise.
        """
        logger.trace(f"Checking if should ignore: path='{path}'")

        # Convert the absolute path to a relative path with forward slashes.
        rel_path = os.path.relpath(path, self.base_dir).replace(os.path.sep, "/")
        logger.trace(f"Converted path to relative path: '{rel_path}'")

        ignore = False
        for pat in self.patterns:
            logger.trace(f"Evaluating pattern: '{pat}' against rel_path: '{rel_path}'")
            if pat.startswith("!"):
                if self._match_pattern(rel_path, pat[1:]):
                    logger.trace(f"Negation pattern '{pat}' matched. Setting ignore to False")
                    ignore = False
            else:
                if self._match_pattern(rel_path, pat):
                    logger.trace(f"Pattern '{pat}' matched. Setting ignore to True")
                    ignore = True

        logger.trace(f"Final ignore decision for path '{path}': {ignore}")
        return ignore
