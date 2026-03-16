"""
Unit tests for CodeAnalyzerConfig and related configuration models.

Strategy: Pure unit tests with no mocks — these are Pydantic models with
file I/O via tmp_path.

Test Responsibilities:
- LoggingConfig: level validation and environment variable setting
- ClassificationConfig: category override validation and lookup
- ApiClientConfig: merge-defaults and set properties
- CodeAnalyzerConfig: JSON file/string round-trip, to_json_file
- load_config_from_cli_arg: with and without path
"""

import json
import os

import pytest

from app.src.codeanalyzer.code_analyzer_config import (
    ApiClientConfig,
    ClassificationConfig,
    CodeAnalyzerConfig,
    LoggingConfig,
    load_config_from_cli_arg,
)

# ---------------------------------------------------------------------------
# LoggingConfig
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACE"])
def test_logging_config_valid_levels(level):
    cfg = LoggingConfig(level=level)
    assert cfg.level == level.upper()


@pytest.mark.parametrize("level", ["debug", "info", "trace"])
def test_logging_config_normalizes_case(level):
    cfg = LoggingConfig(level=level)
    assert cfg.level == level.upper()


def test_logging_config_invalid_level_raises():
    with pytest.raises(Exception):
        LoggingConfig(level="INVALID")


def test_logging_config_none_level():
    cfg = LoggingConfig(level=None)
    assert cfg.level is None


def test_logging_config_apply_to_environment(monkeypatch):
    monkeypatch.delenv("CODETOOLS_LOG_LEVEL", raising=False)
    cfg = LoggingConfig(level="DEBUG")
    cfg.apply_to_environment()
    assert os.environ["CODETOOLS_LOG_LEVEL"] == "DEBUG"


def test_logging_config_apply_none_skips_env(monkeypatch):
    monkeypatch.delenv("CODETOOLS_LOG_LEVEL", raising=False)
    cfg = LoggingConfig(level=None)
    cfg.apply_to_environment()
    assert "CODETOOLS_LOG_LEVEL" not in os.environ


# ---------------------------------------------------------------------------
# ClassificationConfig
# ---------------------------------------------------------------------------


def test_classification_valid_overrides():
    cfg = ClassificationConfig(class_name_overrides={"MyClass": "service"})
    assert cfg.class_name_overrides["MyClass"] == "service"


def test_classification_invalid_category_raises():
    with pytest.raises(Exception):
        ClassificationConfig(class_name_overrides={"MyClass": "not_a_category"})


def test_get_override_found():
    cfg = ClassificationConfig(class_name_overrides={"Foo": "controller"})
    assert cfg.get_class_category_override("Foo") == "controller"


def test_get_override_not_found():
    cfg = ClassificationConfig(class_name_overrides={"Foo": "controller"})
    assert cfg.get_class_category_override("Bar") is None


# ---------------------------------------------------------------------------
# ApiClientConfig
# ---------------------------------------------------------------------------


def test_api_client_config_set_properties():
    cfg = ApiClientConfig()
    assert isinstance(cfg.annotations_set, set)
    assert "FeignClient" in cfg.annotations_set
    assert isinstance(cfg.indicator_types_set, set)
    assert "org.springframework.web.client.RestTemplate" in cfg.indicator_types_set


def test_api_client_config_merge_defaults_with_custom():
    cfg = ApiClientConfig(annotations=["CustomAnno"])
    # Custom annotation is present
    assert "CustomAnno" in cfg.annotations_set
    # Built-in defaults are still present
    assert "FeignClient" in cfg.annotations_set
    assert "RestClient" in cfg.annotations_set


def test_api_client_config_merge_indicator_types_with_custom():
    cfg = ApiClientConfig(indicator_types=["com.custom.MyClient"])
    assert "com.custom.MyClient" in cfg.indicator_types_set
    # Built-in defaults are still present
    assert "org.springframework.web.client.RestTemplate" in cfg.indicator_types_set


# ---------------------------------------------------------------------------
# CodeAnalyzerConfig — JSON file round-trips
# ---------------------------------------------------------------------------


def test_from_json_file_valid(tmp_path):
    config_data = {
        "logging": {"level": "DEBUG"},
        "classification": {"class_name_overrides": {"Foo": "service"}},
    }
    f = tmp_path / "config.json"
    f.write_text(json.dumps(config_data))
    cfg = CodeAnalyzerConfig.from_json_file(str(f))
    assert cfg.logging.level == "DEBUG"
    assert cfg.classification.get_class_category_override("Foo") == "service"


def test_from_json_file_not_found():
    with pytest.raises(FileNotFoundError):
        CodeAnalyzerConfig.from_json_file("/nonexistent/path/config.json")


def test_from_json_file_invalid_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    with pytest.raises(ValueError, match="Invalid JSON"):
        CodeAnalyzerConfig.from_json_file(str(f))


def test_from_json_file_invalid_schema(tmp_path):
    f = tmp_path / "bad_schema.json"
    f.write_text(json.dumps({"logging": {"level": "INVALID_LEVEL"}}))
    with pytest.raises(ValueError):
        CodeAnalyzerConfig.from_json_file(str(f))


# ---------------------------------------------------------------------------
# CodeAnalyzerConfig — JSON string
# ---------------------------------------------------------------------------


def test_from_json_string_valid():
    cfg = CodeAnalyzerConfig.from_json_string('{"logging": {"level": "INFO"}}')
    assert cfg.logging.level == "INFO"


def test_from_json_string_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        CodeAnalyzerConfig.from_json_string("{broken")


def test_from_json_string_invalid_schema():
    with pytest.raises(ValueError):
        CodeAnalyzerConfig.from_json_string('{"logging": {"level": "BOGUS"}}')


# ---------------------------------------------------------------------------
# CodeAnalyzerConfig — to_json_file
# ---------------------------------------------------------------------------


def test_to_json_file(tmp_path):
    cfg = CodeAnalyzerConfig(logging=LoggingConfig(level="WARNING"))
    out = tmp_path / "out.json"
    cfg.to_json_file(str(out))
    loaded = json.loads(out.read_text())
    assert loaded["logging"]["level"] == "WARNING"


# ---------------------------------------------------------------------------
# load_config_from_cli_arg
# ---------------------------------------------------------------------------


def test_load_config_from_cli_arg_with_path(tmp_path, monkeypatch):
    monkeypatch.delenv("CODETOOLS_LOG_LEVEL", raising=False)
    f = tmp_path / "cli.json"
    f.write_text(json.dumps({"logging": {"level": "ERROR"}}))
    cfg = load_config_from_cli_arg(str(f))
    assert cfg.logging.level == "ERROR"
    assert os.environ.get("CODETOOLS_LOG_LEVEL") == "ERROR"


# ---------------------------------------------------------------------------
# Sample config file — schema contract
# ---------------------------------------------------------------------------


def test_sample_config_loads_through_production_path():
    """The committed sample config must parse via the production loader."""
    import pathlib

    # __file__ = app/tests/unit/codeanalyzer/test_code_analyzer_config.py
    # parents[3] = app/
    sample = (
        pathlib.Path(__file__).resolve().parents[3]
        / "src"
        / "codeanalyzer"
        / "codeanalyzer_sample_config.json"
    )
    cfg = CodeAnalyzerConfig.from_json_file(str(sample))
    assert isinstance(cfg, CodeAnalyzerConfig)
    assert cfg.logging.level == "DEBUG"
    assert "FeignClient" in cfg.classification.api_client.annotations_set
    assert (
        "org.springframework.web.client.RestTemplate"
        in cfg.classification.api_client.indicator_types_set
    )


def test_load_config_from_cli_arg_without_path(monkeypatch):
    monkeypatch.delenv("CODETOOLS_LOG_LEVEL", raising=False)
    cfg = load_config_from_cli_arg(None)
    assert cfg.logging.level is None
