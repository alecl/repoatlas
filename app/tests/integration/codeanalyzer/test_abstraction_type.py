"""
Integration tests for abstraction type detection.

Strategy: Real file parsing to test abstraction detection.
Real: Java file parsing, tree-sitter integration, abstraction type detection
Mocked: Nothing

Test Responsibilities:
- Single function tests: Interface and abstract class detection through parsing
"""

from app.src.codeanalyzer.models import AbstractionType, ClassCategory
from app.src.codeanalyzer.parser import JavaParser


def test_parser_detects_interface(tmp_path):
    code = "package com.example; public interface MyInterface {}"
    file_path = tmp_path / "MyInterface.java"
    file_path.write_text(code)
    cls = JavaParser().parse_java_file(str(file_path))
    assert cls.abstraction_type == AbstractionType.INTERFACE
    assert cls.category == ClassCategory.OTHER


def test_parser_detects_abstract_class(tmp_path):
    code = "package com.example; public abstract class MyAbstract {}"
    file_path = tmp_path / "MyAbstract.java"
    file_path.write_text(code)
    cls = JavaParser().parse_java_file(str(file_path))
    assert cls.abstraction_type == AbstractionType.ABSTRACT
    assert cls.category == ClassCategory.OTHER
