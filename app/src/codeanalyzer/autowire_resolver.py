from typing import List, Optional

from app.src.codeanalyzer.type_resolver import TypeResolver
from app.src.logging import logger

from .models import (
    ClassReferenceMemberVariable,
    JavaClass,
    ReferenceScope,
    ResolvedLocation,
)


class AmbiguousBeanReferenceError(Exception):
    """Raised when multiple autowired implementations are found without a qualifier."""

    pass


class AutowireResolver:
    """
    Resolves Spring autowired dependencies to their implementations.
    """

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.type_resolver: TypeResolver = analyzer.type_resolver

    def resolve_all(self) -> bool:
        """Resolve all autowired dependencies."""
        changes_made = False
        for java_class in self.analyzer.classes.values():
            try:
                for member in java_class.get_class_references():
                    if member.is_autowired and member.unresolved_autowire:
                        resolved = self._resolve_autowired_dependency(member, java_class)
                        if resolved:
                            member.resolved_implementation = resolved
                            member.unresolved_autowire.mark_fully_resolved(
                                resolved.fully_qualified_name,
                                ResolvedLocation(
                                    scope=ReferenceScope.SAME_JAR,
                                    class_name=resolved.name,
                                ),
                            )
                            changes_made = True
            except Exception as e:
                logger.error(
                    "Exception while resolving autowired dependencies for class %s: %s",
                    java_class.name,
                    e,
                )
        # Handle constructor‐based injection
        for java_class in self.analyzer.classes.values():
            for ctor in getattr(java_class, "constructors", []):
                if not getattr(ctor, "is_injection", False):
                    continue
                for param in ctor.parameters:
                    interface_class = self.type_resolver.resolve_type(param.type, java_class)
                    if not interface_class:
                        continue
                    implementations = self._find_implementations(interface_class)
                    resolved = None
                    if len(implementations) == 1:
                        resolved = implementations[0]
                    else:
                        resolved = self._find_primary_bean(implementations)
                    if resolved:
                        if not hasattr(java_class, "_constructor_injections"):
                            java_class._constructor_injections = {}
                        java_class._constructor_injections[param.name] = resolved
                        changes_made = True
        return changes_made

    def _resolve_autowired_dependency(
        self, member: ClassReferenceMemberVariable, context_class: JavaClass
    ) -> JavaClass | None:
        interface_class = self.type_resolver.resolve_type(member.type, context_class)
        if not interface_class:
            return None
        implementations = self._find_implementations(interface_class)
        if member.qualifier:
            return self._find_by_qualifier(implementations, member.qualifier)
        elif len(implementations) == 1:
            return implementations[0]
        elif not implementations:
            return None
        else:
            # Multiple candidates: try @Primary
            primary = self._find_primary_bean(implementations)
            if primary:
                return primary
            # ambiguous: multiple impls, no qualifier or primary
            logger.error(
                f"Multiple implementations found for {member.type}: "
                f"{[impl.fully_qualified_name for impl in implementations]}"
            )
            raise AmbiguousBeanReferenceError(
                f"Multiple implementations found for {member.type}: "
                f"{[impl.fully_qualified_name for impl in implementations]}"
            )

    def _find_implementations(self, interface_class: JavaClass) -> list[JavaClass]:
        implementations = []
        for java_class in self.analyzer.classes.values():
            impls = getattr(java_class, "implements", [])
            if interface_class.name in impls or interface_class.fully_qualified_name in impls:
                implementations.append(java_class)
        return implementations

    def _find_by_qualifier(
        self, implementations: list[JavaClass], qualifier: str
    ) -> JavaClass | None:
        for impl in implementations:
            for annotation in getattr(impl, "class_annotations", []):
                if annotation.name == "Qualifier" and annotation.value == qualifier:
                    return impl
                if (
                    annotation.name in ["Component", "Service", "Repository"]
                    and annotation.value == qualifier
                ):
                    return impl
        return None

    def _find_primary_bean(self, implementations: list[JavaClass]) -> JavaClass | None:
        for impl in implementations:
            if any(anno.name == "Primary" for anno in getattr(impl, "class_annotations", [])):
                return impl
        return None
