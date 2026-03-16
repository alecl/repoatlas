from collections.abc import Sequence
from typing import Any, List, Optional

from app.src.codeanalyzer.code_analyzer_config import (
    ApiClientConfig,
    CodeAnalyzerConfig,
)

from .models import (
    Annotation,
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaMethod,
    MemberVariable,
    MemberVariableCategory,
)

# Priority Level Constants
LEVEL_1_SUBSTRINGS = {
    "controller": ClassCategory.CONTROLLER,
    "exception": ClassCategory.EXCEPTION,
    "test": ClassCategory.TEST,
    "aspect": ClassCategory.ASPECT,
    "mapper": ClassCategory.MAPPER,
}

LEVEL_2_SUBSTRINGS = {
    "dao": ClassCategory.DAO,
    "dto": ClassCategory.DTO,
    "repository": ClassCategory.REPOSITORY,
    "entity": ClassCategory.ENTITY,
}

LEVEL_3_SUBSTRINGS = {
    "service": ClassCategory.SERVICE,
    "svc": ClassCategory.SERVICE,
}


def infer_class_category(
    class_name: str,
    annotations: list[Annotation] | None = None,
    #    member_variables: Optional[List[MemberVariable]] = None,
    #    methods: Optional[List[JavaMethod]] = None,
    config: CodeAnalyzerConfig | None = None,
) -> ClassCategory:
    """
    Determine the ClassCategory by inspecting annotations first, then
    by class name suffix, then by substring with priority levels.
    Raises ValueError if substring fallback yields multiple matches at the same priority level.
    """

    # Check configuration overrides first (highest priority)
    if config:
        category_override = config.classification.get_class_category_override(class_name)
        if category_override:
            return ClassCategory(category_override)

    annotations = annotations or []
    anno_names = {a.name for a in annotations}

    # Annotation-driven logic (highest priority)
    if anno_names & {
        "RestController",
        "Controller",
        "ControllerAdvice",
        "RestControllerAdvice",
    }:
        return ClassCategory.CONTROLLER
    if "Service" in anno_names:
        return ClassCategory.SERVICE
    if anno_names & {"Repository", "RepositoryRestResource"}:
        return ClassCategory.REPOSITORY
    if anno_names & {"Entity", "Table"}:
        return ClassCategory.ENTITY
    if "Mapper" in anno_names:
        return ClassCategory.MAPPER
    if "Aspect" in anno_names:
        return ClassCategory.ASPECT
    # Optional custom @Dao annotation
    if "Dao" in anno_names:
        return ClassCategory.DAO

    # Name-driven fallback: exact suffix match (stronger than substring)
    all_substrings_map = {}
    all_substrings_map.update(LEVEL_1_SUBSTRINGS)
    all_substrings_map.update(LEVEL_2_SUBSTRINGS)
    all_substrings_map.update(LEVEL_3_SUBSTRINGS)

    lname = class_name.lower()
    for suffix, category in all_substrings_map.items():
        if lname.endswith(suffix):
            return category

    # Next: substring-match by priority level, one level at a time
    for level, level_map in [
        (1, LEVEL_1_SUBSTRINGS),
        (2, LEVEL_2_SUBSTRINGS),
        (3, LEVEL_3_SUBSTRINGS),
    ]:
        matches = [cat for substr, cat in level_map.items() if substr in lname]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"Multiple category matches at priority level {level} for {class_name}: {matches}"
            )

    # Nothing matched → OTHER
    return ClassCategory.OTHER


def infer_api_client_category(
    class_name: str,
    annotations: list[Annotation] | None = None,
    member_variables: list[MemberVariable] | None = None,
    methods: Sequence[Any] | None = None,
    config: CodeAnalyzerConfig | None = None,
) -> ClassCategory | None:
    """Second-pass API client detection."""
    config = config or CodeAnalyzerConfig()
    api_config = config.classification.api_client

    # Rule 1: Check annotations
    if annotations:
        anno_names = {a.name for a in annotations}
        if anno_names & api_config.annotations_set:
            return ClassCategory.API_CLIENT

    # TODO - we aren't capturing constructors and that's where RestTemplate is. Fundamental additional needed.
    # Rule 2: Check constructor parameters
    if methods:
        for method in methods:
            if method.name == class_name:
                for param in method.parameters:
                    # Prefer fully‐qualified when set, otherwise simple type
                    fqn = param.fqn_type or param.type
                    simple = fqn.split(".")[-1]
                    if fqn in api_config.indicator_types_set or simple in {
                        t.split(".")[-1] for t in api_config.indicator_types
                    }:
                        return ClassCategory.API_CLIENT

    # Rule 3: Check member variables
    if member_variables:
        for var in member_variables:
            if isinstance(var, ClassReferenceMemberVariable):
                # Prefer FQN if resolved, else simple type
                fqn = var.fqn_type or var.type
                simple = fqn.split(".")[-1]
                # match either exact FQN or simple name from our configured libraries
                if fqn in api_config.indicator_types_set or simple in {
                    t.split(".")[-1] for t in api_config.indicator_types_set
                }:
                    return ClassCategory.API_CLIENT

    return None  # Not an API client


def infer_member_variable_category(type_text: str) -> MemberVariableCategory:
    """
    Determine the category of a member variable based on its type.

    Args:
        type_text: The type of the variable

    Returns:
        MemberVariableCategory
    """
    # Check for primitives
    primitives = [
        "int",
        "long",
        "float",
        "double",
        "boolean",
        "char",
        "byte",
        "short",
        "void",
    ]
    if any(primitive in type_text.lower() for primitive in primitives):
        return MemberVariableCategory.PRIMITIVE

    # Check for collections
    collections = [
        "List",
        "Set",
        "Queue",
        "Deque",
        "Collection",
        "Iterable",
        "ArrayList",
        "HashSet",
        "LinkedList",
    ]
    if any(collection in type_text for collection in collections):
        return MemberVariableCategory.COLLECTION

    # Check for maps
    if "Map" in type_text or "HashMap" in type_text or "TreeMap" in type_text:
        return MemberVariableCategory.MAP

    # Else if starts uppercase, class reference
    if type_text and type_text[0].isupper():
        return MemberVariableCategory.CLASS_REFERENCE

    return MemberVariableCategory.OTHER
