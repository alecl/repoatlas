"""
Unit tests for JavaAnalyzer.refresh_class_if_needed.

Strategy: Uses tmp_path with real Java files — no mocks for the file-system
change-detection logic. The method's core value is detecting file changes via
a size → mtime → CRC32 → MD5 cascade, so real file I/O is essential.

Test Responsibilities:
- File-change detection cascade (size, mtime, CRC32, MD5)
- Cycle detection and recursion
- Dependency direction (upstream/downstream)
- Scope, category, and package filtering
"""

import os
import zlib
from hashlib import md5

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.models import (
    ClassCategory,
    DependencyOptions,
    JavaClass,
    ReferenceScope,
    ResolvedLocation,
)

SIMPLE_JAVA = """\
package com.example;
public class Simple {
    public void hello() {}
}
"""

MODIFIED_JAVA = """\
package com.example;
public class Simple {
    public void hello() { return; }
    public void goodbye() {}
}
"""

SERVICE_JAVA = """\
package com.example;
public class MyService {
    public void serve() {}
}
"""


def _write_and_parse(analyzer, tmp_path, filename, content):
    """Write a Java file and parse it; return the parsed class."""
    f = tmp_path / filename
    f.write_text(content)
    return analyzer.parse_file(str(f))


def _set_metadata(java_class, file_path):
    """Set file metadata on a JavaClass from the current file state."""
    st = os.stat(file_path)
    java_class.file_size = st.st_size
    java_class.last_modified = st.st_mtime
    with open(file_path, "rb") as fh:
        data = fh.read()
    java_class.crc32_hash = zlib.crc32(data)
    java_class.md5_hash = md5(data).hexdigest()


# ---------------------------------------------------------------------------
# Basic / edge cases
# ---------------------------------------------------------------------------


def test_refresh_nonexistent_class(tmp_path):
    analyzer = JavaAnalyzer()
    refreshed, deps = analyzer.refresh_class_if_needed("com.nonexistent.Foo")
    assert refreshed is False
    assert deps == []


def test_refresh_no_absolute_path(tmp_path):
    analyzer = JavaAnalyzer()
    cls = JavaClass(name="NoPath", package="com.example", absolute_path="")
    analyzer.classes[cls.fully_qualified_name] = cls
    refreshed, deps = analyzer.refresh_class_if_needed(cls.fully_qualified_name)
    assert refreshed is False


def test_refresh_file_deleted(tmp_path):
    analyzer = JavaAnalyzer()
    f = tmp_path / "Gone.java"
    f.write_text(SIMPLE_JAVA)
    java_class = analyzer.parse_file(str(f))
    fqn = java_class.fully_qualified_name
    f.unlink()
    refreshed, deps = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is False


def test_refresh_cycle_detection(tmp_path):
    analyzer = JavaAnalyzer()
    java_class = _write_and_parse(analyzer, tmp_path, "Simple.java", SIMPLE_JAVA)
    fqn = java_class.fully_qualified_name
    # Pre-populate visited_classes to simulate a cycle
    refreshed, deps = analyzer.refresh_class_if_needed(fqn, visited_classes={fqn})
    assert refreshed is False


# ---------------------------------------------------------------------------
# File-change detection cascade
# ---------------------------------------------------------------------------


def test_refresh_no_metadata_triggers_reparse(tmp_path):
    """When all metadata hashes are cleared, mismatch triggers reparse."""
    analyzer = JavaAnalyzer()
    java_class = _write_and_parse(analyzer, tmp_path, "Simple.java", SIMPLE_JAVA)
    fqn = java_class.fully_qualified_name
    # Clear all metadata — size mismatch enters cascade, cleared hashes force reparse
    java_class.file_size = None
    java_class.last_modified = None
    java_class.crc32_hash = None
    java_class.md5_hash = None
    refreshed, _ = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is True


def test_refresh_unchanged_file_no_reparse(tmp_path):
    """Matching size + mtime → no reparse."""
    analyzer = JavaAnalyzer()
    java_class = _write_and_parse(analyzer, tmp_path, "Simple.java", SIMPLE_JAVA)
    fqn = java_class.fully_qualified_name
    _set_metadata(java_class, java_class.absolute_path)
    refreshed, _ = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is False


def test_refresh_changed_size_different_content(tmp_path):
    """File size changed + different content → reparse."""
    analyzer = JavaAnalyzer()
    f = tmp_path / "Simple.java"
    f.write_text(SIMPLE_JAVA)
    java_class = analyzer.parse_file(str(f))
    fqn = java_class.fully_qualified_name
    _set_metadata(java_class, str(f))
    # Now modify the file
    f.write_text(MODIFIED_JAVA)
    refreshed, _ = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is True
    # Verify new class has the new method
    new_class = analyzer.classes[fqn]
    method_names = [m.name for m in new_class.methods]
    assert "goodbye" in method_names


def test_refresh_crc32_match_stops_early(tmp_path):
    """Wrong mtime but matching CRC32 → no reparse."""
    analyzer = JavaAnalyzer()
    f = tmp_path / "Simple.java"
    f.write_text(SIMPLE_JAVA)
    java_class = analyzer.parse_file(str(f))
    fqn = java_class.fully_qualified_name
    _set_metadata(java_class, str(f))
    # Fake a different mtime but same content (CRC32 will match)
    java_class.last_modified = java_class.last_modified - 100
    refreshed, _ = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is False


def test_refresh_md5_match_stops_early(tmp_path):
    """Wrong CRC32 but matching MD5 → no reparse."""
    analyzer = JavaAnalyzer()
    f = tmp_path / "Simple.java"
    f.write_text(SIMPLE_JAVA)
    java_class = analyzer.parse_file(str(f))
    fqn = java_class.fully_qualified_name
    _set_metadata(java_class, str(f))
    # Fake a different mtime and CRC32 but keep MD5 (which still matches content)
    java_class.last_modified = java_class.last_modified - 100
    java_class.crc32_hash = 0xDEADBEEF
    refreshed, _ = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is False


def test_refresh_actual_file_change_replaces_class(tmp_path):
    """Real file modification → class replaced in registry."""
    analyzer = JavaAnalyzer()
    f = tmp_path / "Simple.java"
    f.write_text(SIMPLE_JAVA)
    java_class = analyzer.parse_file(str(f))
    fqn = java_class.fully_qualified_name
    _set_metadata(java_class, str(f))
    old_id = id(analyzer.classes[fqn])
    # Modify the file
    f.write_text(MODIFIED_JAVA)
    refreshed, _ = analyzer.refresh_class_if_needed(fqn)
    assert refreshed is True
    assert id(analyzer.classes[fqn]) != old_id


# ---------------------------------------------------------------------------
# load_source
# ---------------------------------------------------------------------------


def test_refresh_load_source_on_unchanged_file(tmp_path):
    """load_source=True on unchanged file populates source_code."""
    analyzer = JavaAnalyzer()
    f = tmp_path / "Simple.java"
    f.write_text(SIMPLE_JAVA)
    java_class = analyzer.parse_file(str(f))
    fqn = java_class.fully_qualified_name
    _set_metadata(java_class, str(f))
    # Source not loaded yet
    assert not java_class.source_code
    refreshed, _ = analyzer.refresh_class_if_needed(fqn, load_source=True)
    assert refreshed is False
    assert analyzer.classes[fqn].source_code == SIMPLE_JAVA


# ---------------------------------------------------------------------------
# Dependency refresh controls
# ---------------------------------------------------------------------------


def test_refresh_no_dependency_refresh_stops(tmp_path):
    """refresh_dependent_classes=False → no dependency scanning."""
    analyzer = JavaAnalyzer()
    java_class = _write_and_parse(analyzer, tmp_path, "Simple.java", SIMPLE_JAVA)
    fqn = java_class.fully_qualified_name
    # Clear all metadata to trigger reparse
    java_class.file_size = None
    java_class.last_modified = None
    java_class.crc32_hash = None
    java_class.md5_hash = None
    refreshed, deps = analyzer.refresh_class_if_needed(fqn, refresh_dependent_classes=False)
    assert refreshed is True
    assert deps == []


def test_refresh_max_depth_zero_stops(tmp_path):
    """DependencyOptions(max_depth=0) → no dependency scanning."""
    analyzer = JavaAnalyzer()
    java_class = _write_and_parse(analyzer, tmp_path, "Simple.java", SIMPLE_JAVA)
    fqn = java_class.fully_qualified_name
    refreshed, deps = analyzer.refresh_class_if_needed(
        fqn,
        refresh_dependent_classes=True,
        dependency_options=DependencyOptions(max_depth=0),
    )
    assert deps == []


# ---------------------------------------------------------------------------
# Upstream dependency refresh
# ---------------------------------------------------------------------------


def test_refresh_upstream_dependencies(tmp_path):
    """Controller→Service member variable triggers upstream refresh."""
    analyzer = JavaAnalyzer()

    # Parse service
    svc_file = tmp_path / "MyService.java"
    svc_file.write_text(SERVICE_JAVA)
    svc_class = analyzer.parse_file(str(svc_file))
    _set_metadata(svc_class, str(svc_file))

    # Parse controller with a member variable referencing MyService
    ctrl_java = """\
package com.example;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class MyController {
    private MyService myService;
}
"""
    ctrl_file = tmp_path / "MyController.java"
    ctrl_file.write_text(ctrl_java)
    ctrl_class = analyzer.parse_file(str(ctrl_file))
    _set_metadata(ctrl_class, str(ctrl_file))

    # Now modify the service file
    svc_file.write_text(SERVICE_JAVA + "\n// changed")

    options = DependencyOptions(upstream=True, downstream=False, max_depth=2)
    refreshed, deps = analyzer.refresh_class_if_needed(
        ctrl_class.fully_qualified_name,
        refresh_dependent_classes=True,
        dependency_options=options,
    )
    # Controller itself was not changed (metadata matches), but service was
    assert refreshed is False


# ---------------------------------------------------------------------------
# Downstream dependency refresh
# ---------------------------------------------------------------------------


def test_refresh_downstream_dependencies(tmp_path):
    """Find classes that reference this one via member variables."""
    analyzer = JavaAnalyzer()

    # Parse service
    svc_file = tmp_path / "MyService.java"
    svc_file.write_text(SERVICE_JAVA)
    svc_class = analyzer.parse_file(str(svc_file))

    # Parse controller referencing service
    ctrl_java = """\
package com.example;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class MyController {
    private MyService myService;
}
"""
    ctrl_file = tmp_path / "MyController.java"
    ctrl_file.write_text(ctrl_java)
    ctrl_class = analyzer.parse_file(str(ctrl_file))
    _set_metadata(ctrl_class, str(ctrl_file))

    options = DependencyOptions(upstream=False, downstream=True, max_depth=2)
    # Clear all metadata so service triggers reparse, then finds controller as downstream
    svc_class.file_size = None
    svc_class.last_modified = None
    svc_class.crc32_hash = None
    svc_class.md5_hash = None
    refreshed, deps = analyzer.refresh_class_if_needed(
        svc_class.fully_qualified_name,
        refresh_dependent_classes=True,
        dependency_options=options,
    )
    assert refreshed is True


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_refresh_scope_filtering(tmp_path):
    """Exclude scope prevents dependency from being refreshed."""
    analyzer = JavaAnalyzer()
    svc_file = tmp_path / "MyService.java"
    svc_file.write_text(SERVICE_JAVA)
    svc_class = analyzer.parse_file(str(svc_file))
    _set_metadata(svc_class, str(svc_file))
    # Tag service with a scope that is excluded
    svc_class.resolved_location = ResolvedLocation(scope=ReferenceScope.THIRD_PARTY)

    ctrl_java = """\
package com.example;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class MyController {
    private MyService myService;
}
"""
    ctrl_file = tmp_path / "MyController.java"
    ctrl_file.write_text(ctrl_java)
    ctrl_class = analyzer.parse_file(str(ctrl_file))
    _set_metadata(ctrl_class, str(ctrl_file))

    options = DependencyOptions(
        upstream=True,
        downstream=False,
        max_depth=2,
        exclude_scopes=[ReferenceScope.THIRD_PARTY],
    )
    # Modify service so it would be refreshed if not filtered
    svc_file.write_text(SERVICE_JAVA + "\n// changed")
    _, deps = analyzer.refresh_class_if_needed(
        ctrl_class.fully_qualified_name,
        refresh_dependent_classes=True,
        dependency_options=options,
    )
    # Service should be excluded, so not in deps
    assert svc_class.fully_qualified_name not in deps


def test_refresh_category_filtering(tmp_path):
    """Exclude category prevents dependency from being refreshed."""
    analyzer = JavaAnalyzer()
    svc_file = tmp_path / "MyService.java"
    svc_file.write_text(SERVICE_JAVA)
    svc_class = analyzer.parse_file(str(svc_file))
    _set_metadata(svc_class, str(svc_file))

    ctrl_java = """\
package com.example;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class MyController {
    private MyService myService;
}
"""
    ctrl_file = tmp_path / "MyController.java"
    ctrl_file.write_text(ctrl_java)
    ctrl_class = analyzer.parse_file(str(ctrl_file))
    _set_metadata(ctrl_class, str(ctrl_file))

    # Exclude SERVICE category (MyService is classified as SERVICE by name)
    options = DependencyOptions(
        upstream=True,
        downstream=False,
        max_depth=2,
        exclude_categories=[ClassCategory.SERVICE],
    )
    svc_file.write_text(SERVICE_JAVA + "\n// changed")
    _, deps = analyzer.refresh_class_if_needed(
        ctrl_class.fully_qualified_name,
        refresh_dependent_classes=True,
        dependency_options=options,
    )
    assert svc_class.fully_qualified_name not in deps


def test_refresh_package_filtering(tmp_path):
    """Exclude by package prefix prevents dependency from being refreshed."""
    analyzer = JavaAnalyzer()
    svc_file = tmp_path / "MyService.java"
    svc_file.write_text(SERVICE_JAVA)
    svc_class = analyzer.parse_file(str(svc_file))
    _set_metadata(svc_class, str(svc_file))

    ctrl_java = """\
package com.example;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class MyController {
    private MyService myService;
}
"""
    ctrl_file = tmp_path / "MyController.java"
    ctrl_file.write_text(ctrl_java)
    ctrl_class = analyzer.parse_file(str(ctrl_file))
    _set_metadata(ctrl_class, str(ctrl_file))

    options = DependencyOptions(
        upstream=True,
        downstream=False,
        max_depth=2,
        exclude_packages=["com.example"],
    )
    svc_file.write_text(SERVICE_JAVA + "\n// changed")
    _, deps = analyzer.refresh_class_if_needed(
        ctrl_class.fully_qualified_name,
        refresh_dependent_classes=True,
        dependency_options=options,
    )
    assert svc_class.fully_qualified_name not in deps
