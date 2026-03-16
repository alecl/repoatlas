"""
Unit tests for blank line collapse utility function.

Strategy: Pure unit tests with string inputs.
Real: String manipulation algorithms
Mocked: Nothing (pure string processing function)

Test Responsibilities:
- Parameterized tests: Various collapse scenarios with different line endings
- Edge case tests: Indentation preservation, whitespace handling for code lines
"""

import pytest

# adjust this import to wherever you have collapse_blank_lines defined
from app.src.codeanalyzer.util import collapse_blank_lines


@pytest.mark.parametrize(
    "input_text, expected",
    [
        # 1) No blank lines → unchanged
        ("a\nb", "a\nb"),
        # 2) Simple collapse of 3→1
        ("a\n\n\nb", "a\n\nb"),
        # 3) Whitespace-only lines count as blank
        ("a\n  \n\t\n\nb", "a\n\nb"),
        # 4) Mixed CRLF (\r\n) line endings
        ("a\r\n\r\n\r\nb", "a\n\nb"),
        # 5) Exactly one blank line stays one
        ("a\n\nb", "a\n\nb"),
        # 6) Trailing blank lines collapse to one
        ("a\n\n\n", "a\n\n"),
        # 7) Leading blank lines collapse to one
        ("\n\n\nfoo", "\n\nfoo"),
        # 8) Mixed line endings + spaces
        ("a\r\n \r\n\n\nb", "a\n\nb"),
        # 9) Multiple segments
        ("one\n\n\n\ntwo\n\n\nthree", "one\n\ntwo\n\nthree"),
    ],
)
def test_various_collapses(input_text, expected):
    assert collapse_blank_lines(input_text) == expected


def test_indentation_preserved_on_code_lines():
    java_snippet = (
        "public class C {\r\n"
        "\r\n"
        "    @GetMapping\n"
        "    public void m() {\n"
        "        // something\n"
        "    }\n"
        "\n"
        "\n"
        "    // comment between methods\n"
        "\n"
        "\n"
        "    public void n() {}\n"
        "}\n"
    )
    cleaned = collapse_blank_lines(java_snippet)
    # there should be exactly one blank line between blocks,
    # and the indentation on the "    }" line must remain
    assert "    }\n\n    // comment" in cleaned
    # the very first blank run collapses to one
    assert cleaned.startswith("public class C {\n\n")


def test_no_extra_whitespace_or_trailing_spaces():
    text = "line\n\n\n   \n\nend"
    out = collapse_blank_lines(text)
    assert out.count("\n\n") == 1
