"""
Configuration model for the code analyzer using Pydantic.
Supports loading from JSON files and environment variable management.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

import json5
from pydantic import BaseModel, Field, field_validator, model_validator


class LoggingConfig(BaseModel):
    """Configuration for logging settings."""

    level: str | None = Field(None, description="Log level (DEBUG, INFO, WARNING, ERROR, TRACE)")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v):
        if v is not None:
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACE"}
            if v.upper() not in valid_levels:
                raise ValueError(f"Invalid log level '{v}'. Must be one of: {valid_levels}")
            return v.upper()
        return v

    def apply_to_environment(self):
        """Set the CODETOOLS_LOG_LEVEL environment variable if configured."""
        if self.level:
            os.environ["CODETOOLS_LOG_LEVEL"] = self.level


class ApiClientConfig(BaseModel):
    """Configuration for API client detection rules."""

    annotations: list[str] = Field(
        default_factory=lambda: [
            "FeignClient",
            "RestClient",
            "GraphQLApi",
            "WebServiceClient",
            "ApiClient",
        ],
        description="Annotations that indicate a class is an API client",
    )

    indicator_types: list[str] = Field(
        default_factory=lambda: [
            "java.net.http.HttpClient",
            "org.apache.http.client.HttpClient",
            "okhttp3.OkHttpClient",
            "org.asynchttpclient.AsyncHttpClient",
            "org.eclipse.jetty.client.HttpClient",
            "com.apollographql.apollo.ApolloClient",
            "com.netflix.graphql.dgs.client.GraphQLClient",
            "org.springframework.graphql.client.GraphQlClient",
            "io.grpc.ManagedChannel",
            "io.grpc.ManagedChannelBuilder",
            "org.apache.thrift.TServiceClient",
            "org.apache.thrift.transport.TSocket",
            "org.apache.thrift.transport.THttpClient",
            "org.springframework.web.client.RestTemplate",
            "org.springframework.boot.web.client.RestTemplateBuilder",
        ],
        description="Member, constructor, or method types that indicate a class is an API client",
    )

    @property
    def annotations_set(self) -> set[str]:
        """Get annotations as a set for fast lookup."""
        return set(self.annotations)

    @property
    def indicator_types_set(self) -> set[str]:
        """
        Get combined constructor and member variable types as a set
        for API client detection.
        """
        return set(self.indicator_types)

    @model_validator(mode="after")
    def _merge_defaults(self) -> "ApiClientConfig":
        """
        Merge user-provided annotations and indicator_types with built-in defaults.
        """
        # Built-in defaults
        default_annos = {
            "FeignClient",
            "RestClient",
            "GraphQLApi",
            "WebServiceClient",
            "ApiClient",
        }
        default_inds = {
            "java.net.http.HttpClient",
            "org.apache.http.client.HttpClient",
            "okhttp3.OkHttpClient",
            "org.asynchttpclient.AsyncHttpClient",
            "org.eclipse.jetty.client.HttpClient",
            "com.apollographql.apollo.ApolloClient",
            "com.netflix.graphql.dgs.client.GraphQLClient",
            "org.springframework.graphql.client.GraphQlClient",
            "io.grpc.ManagedChannel",
            "io.grpc.ManagedChannelBuilder",
            "org.apache.thrift.TServiceClient",
            "org.apache.thrift.transport.TSocket",
            "org.apache.thrift.transport.THttpClient",
            "org.springframework.web.client.RestTemplate",
            "org.springframework.boot.web.client.RestTemplateBuilder",
        }
        # Merge annotations
        merged_annos = list(default_annos)
        for a in self.annotations:
            if a not in default_annos:
                merged_annos.append(a)
        self.annotations = merged_annos
        # Merge indicator types
        merged_inds = list(default_inds)
        for t in self.indicator_types:
            if t not in default_inds:
                merged_inds.append(t)
        self.indicator_types = merged_inds
        return self


class ClassificationConfig(BaseModel):
    """Configuration for class classification rules."""

    class_name_overrides: dict[str, str] = Field(
        default_factory=dict, description="Override class category by simple class name"
    )

    api_client: ApiClientConfig = Field(
        default_factory=ApiClientConfig,
        description="API client detection configuration",
    )

    @field_validator("class_name_overrides")
    @classmethod
    def validate_category_values(cls, v):
        """Validate that category values are valid ClassCategory enum values."""
        from .models import ClassCategory

        valid_categories = {category.value for category in ClassCategory}
        for class_name, category in v.items():
            if category not in valid_categories:
                raise ValueError(
                    f"Invalid category '{category}' for class '{class_name}'. "
                    f"Must be one of: {valid_categories}"
                )
        return v

    #    def get_class_category_override(self, class_name: str, fully_qualified_name: str) -> Optional[str]:
    def get_class_category_override(self, class_name: str) -> str | None:
        """
        Get category override for a class, checking FQN first, then simple name.

        Args:
            class_name: Simple class name

        Returns:
            Category string if override found, None otherwise
        """
        # Check simple class name
        if class_name in self.class_name_overrides:
            return self.class_name_overrides[class_name]

        return None


class CodeAnalyzerConfig(BaseModel):
    """Main configuration for the code analyzer."""

    logging: LoggingConfig = Field(
        default_factory=lambda: LoggingConfig(level=None),
        description="Logging configuration",
    )

    classification: ClassificationConfig = Field(
        default_factory=lambda: ClassificationConfig(),
        description="Class classification configuration",
    )

    @classmethod
    def from_json_file(cls, file_path: str) -> "CodeAnalyzerConfig":
        """
        Load configuration from a JSON file.

        Args:
            file_path: Path to the JSON configuration file

        Returns:
            CodeAnalyzerConfig instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the JSON is invalid or doesn't match the schema
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(path, encoding="utf-8") as f:
                config_data = json5.load(f)
            return cls(**config_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}") from e
        except ValueError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}") from e
        except Exception as e:
            raise ValueError(f"Invalid configuration format: {e}") from e

    @classmethod
    def from_json_string(cls, json_str: str) -> "CodeAnalyzerConfig":
        """
        Load configuration from a JSON string.

        Args:
            json_str: JSON configuration as string

        Returns:
            CodeAnalyzerConfig instance
        """
        try:
            config_data = json.loads(json_str)
            return cls(**config_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}") from e
        except Exception as e:
            raise ValueError(f"Invalid configuration format: {e}") from e

    def apply_logging_settings(self):
        """Apply logging settings to the environment."""
        self.logging.apply_to_environment()

    def to_json_file(self, file_path: str, indent: int = 2):
        """
        Save configuration to a JSON file.

        Args:
            file_path: Path where to save the configuration
            indent: JSON indentation for readability
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.dict(), f, indent=indent)


# Convenience function for common usage
def load_config_from_cli_arg(config_path: str | None = None) -> CodeAnalyzerConfig:
    """
    Load configuration from CLI argument or return default config.

    Args:
        config_path: Optional path to configuration file from CLI

    Returns:
        CodeAnalyzerConfig instance
    """
    if config_path:
        config = CodeAnalyzerConfig.from_json_file(config_path)
        config.apply_logging_settings()
        return config
    else:
        # Return default configuration
        config = CodeAnalyzerConfig()
        config.apply_logging_settings()
        return config
