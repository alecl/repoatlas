import json
import sys

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.code_visualizer import CodeVisualizer
from app.src.codeanalyzer.parser import JavaParser


# Renamed function from test_file to run_parser_test to avoid pytest discovery
def run_parser_test(file_path, constants_path=None):
    parser = JavaParser()
    java_class = parser.parse_java_file(file_path)

    # Create analyzer
    analyzer = JavaAnalyzer()
    analyzer.classes[java_class.fully_qualified_name] = java_class

    # Load constants if provided
    if constants_path:
        with open(constants_path) as f:
            constants = json.load(f)
            analyzer.add_constants(constants)

    print(CodeVisualizer.format_text([java_class]))

    print(f"Class: {java_class.name}")
    print(f"Package: {java_class.package}")
    print(f"Category: {java_class.category}")
    print(
        f"Base Path: {java_class.base_endpoint_path if hasattr(java_class, 'base_endpoint_path') else 'N/A'}"
    )

    if hasattr(java_class, "service_variables"):
        print(f"Service Variables: {[v.name for v in java_class.service_variables]}")

    if hasattr(java_class, "get_all_endpoints"):
        endpoints = java_class.get_all_endpoints()
        print(f"Endpoints: {endpoints}")


# Test the files
if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        constants_path = sys.argv[2] if len(sys.argv) > 2 else None
        run_parser_test(file_path, constants_path)
    else:
        print("Usage: python test_parser.py <java_file_path> [constants_path]")
