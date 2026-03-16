from typing import Optional

from .models import (
    Annotation,
    JavaClass,
    ReferenceScope,
    ResolvedLocation,
    UnresolvedConstant,
)


class ConstantResolver:
    """
    Resolves constant references to their actual values.

    This resolver is designed for batch, stateful resolution of constants in Java classes.
    When you call `resolve_all` or related methods, it will mutate the analyzer and class state,
    marking constants as resolved and updating annotation values. This is efficient for large-scale
    analysis, but should not be used for ad-hoc inspection or debugging.

    For direct, read-only inspection of what a constant or expression would resolve to (without
    mutating any state), use the `peek_expression_value` method.
    """

    def __init__(self, analyzer):
        self.analyzer = analyzer
        # Allow tests to pass a fake analyzer without import_resolver
        self.import_resolver = getattr(analyzer, "import_resolver", None)

    def resolve_all(self) -> bool:
        """
        Resolve all unresolved constants in the analyzer's classes.

        This method mutates the analyzer and class state, updating annotation values and
        marking constants as resolved. It is efficient for batch analysis, but should not
        be used for direct inspection or debugging.

        Returns:
            True if any changes were made, False otherwise.
        """
        changes_made = False
        for java_class in self.analyzer.classes.values():
            changes_made |= self._resolve_class_constants(java_class)
        return changes_made

    def _resolve_class_constants(self, java_class: JavaClass) -> bool:
        """
        Resolve all unresolved constants in a single Java class.

        This method mutates the class state, updating annotation values and marking
        constants as resolved.

        Returns:
            True if any changes were made, False otherwise.
        """
        changes_made = False
        # Resolve in annotations
        for annotation in self._get_all_annotations(java_class):
            for key, unresolved in list(annotation.unresolved_values.items()):
                resolved_value = self._resolve_constant_chain(unresolved, java_class)
                if resolved_value:
                    annotation.values[key] = resolved_value
                    unresolved.mark_fully_resolved(
                        resolved_value,
                        ResolvedLocation(
                            scope=ReferenceScope.SAME_JAR, class_name=java_class.name
                        ),
                    )
                    # Record this resolution for later source‐level replacement
                    java_class.resolved_references.append(unresolved)
                    del annotation.unresolved_values[key]
                    changes_made = True
        return changes_made

    def _get_all_annotations(self, java_class: JavaClass):
        # Collect all annotations from class, member variables, and methods
        for annotation in java_class.class_annotations:
            yield annotation
        for var in java_class.member_variables:
            for annotation in getattr(var, "annotations", []):
                yield annotation
        for method in java_class.methods:
            for annotation in getattr(method, "annotations", []):
                yield annotation

    def _resolve_constant_chain(
        self, unresolved: UnresolvedConstant, context_class: JavaClass
    ) -> str | None:
        """
        Resolve a chain of constant references, including cross-class and chained references.

        This method mutates the unresolved reference and may update analyzer/class state.
        """
        unresolved.add_resolution_attempt("constant_chain", False)
        resolution_chain = []
        current_ref = unresolved.raw_value
        max_depth = 10
        for _depth in range(max_depth):
            if "." not in current_ref:
                # Try local constant first
                value = context_class.constants.get(current_ref)
                # Try global constants if not found locally
                if value is None and hasattr(self.analyzer, "global_constants"):
                    value = self.analyzer.global_constants.get(current_ref)
            else:
                class_ref, field_name = current_ref.rsplit(".", 1)
                target_class = self._resolve_class_reference(class_ref, context_class)
                value = None
                if target_class:
                    value = target_class.constants.get(field_name)
                # Try global constants if not found in class
                if value is None and hasattr(self.analyzer, "global_constants"):
                    value = self.analyzer.global_constants.get(current_ref)
                if not target_class and value is None:
                    unresolved.add_resolution_attempt(
                        "constant_chain",
                        False,
                        error_message=f"Cannot resolve class: {class_ref}",
                        partial_result={"resolution_chain": resolution_chain},
                    )
                    return None
            if value is None:
                return None
            resolution_chain.append((current_ref, value))
            if self._looks_like_constant_reference(value):
                current_ref = value
                continue
            else:
                unresolved.add_resolution_attempt("constant_chain", True)
                return value
        return None

    def _resolve_class_reference(
        self, class_ref: str, context_class: JavaClass
    ) -> JavaClass | None:
        # Try to find the class in our parsed classes
        for fqn, java_class in self.analyzer.classes.items():
            if java_class.name == class_ref or fqn == class_ref or fqn.endswith(f".{class_ref}"):
                return java_class
        # Try same package
        potential_fqn = f"{context_class.package}.{class_ref}"
        if potential_fqn in self.analyzer.classes:
            return self.analyzer.classes[potential_fqn]
        return None

    def _looks_like_constant_reference(self, value: str) -> bool:
        if not isinstance(value, str):
            return False
        value = value.strip()
        return bool(
            "." in value
            and not value.startswith(("/", '"', "'"))
            and value.lower() not in ("true", "false")
        )

    def peek_expression_value(self, class_name: str, expr: str) -> str | None:
        """
        Recursively look up the value of a constant expression (e.g., 'A.B.C'),
        following chains, but do not mutate any state.

        This method is intended for direct inspection, debugging, or test usage.
        It is not efficient for large-scale or repeated analysis, as it does not
        cache or update any analyzer or class state. For batch or production use,
        prefer the stateful `resolve_all` and related methods.

        Args:
            class_name: The name of the class to use as context for local constants.
            expr: The constant expression to evaluate.

        Returns:
            The resolved value as a string, or None if not found.
        """
        java_class = self.analyzer.find_unique_class_by_name(class_name)
        current_expr = expr
        max_depth = 10
        for _ in range(max_depth):
            # Try local constant
            if java_class and current_expr in java_class.constants:
                value = java_class.constants[current_expr]
            # Try global constant
            elif (
                hasattr(self.analyzer, "global_constants")
                and current_expr in self.analyzer.global_constants
            ):
                value = self.analyzer.global_constants[current_expr]
            # Try chained reference
            elif "." in current_expr:
                class_ref, field_name = current_expr.rsplit(".", 1)
                target_class = self._resolve_class_reference(class_ref, java_class)
                if target_class and field_name in target_class.constants:
                    value = target_class.constants[field_name]
                else:
                    # If the chain cannot be resolved, return the original expression
                    return current_expr
            else:
                # If not found anywhere, return the original expression
                return current_expr
            # If the value is not a string or is the same as the current expression, return it
            if not isinstance(value, str) or value == current_expr:
                return value
            current_expr = value
        return current_expr
