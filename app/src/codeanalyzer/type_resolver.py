from typing import Optional, Tuple

from .models import ClassReferenceMemberVariable, JavaClass

# Known Java lang types which should not use wildcard imports
JDK_TYPES = {
    "String",
    "Integer",
    "Long",
    "Boolean",
    "Object",
    "Exception",
    "Byte",
    "Short",
    "Character",
    "Double",
    "Float",
}


class TypeResolver:
    def __init__(self, analyzer):
        self.analyzer = analyzer

    def resolve_all(self) -> bool:
        """Resolve all unresolved type references."""
        changes_made = False
        for java_class in self.analyzer.classes.values():
            for member in java_class.member_variables:
                if isinstance(member, ClassReferenceMemberVariable) and member.unresolved_type:
                    resolved_class = self.resolve_type(member.type, java_class)
                    if resolved_class:
                        member.resolved_class = resolved_class
                        member.unresolved_type.mark_fully_resolved(
                            resolved_class.fully_qualified_name, None
                        )
                        changes_made = True
        return changes_made

    def resolve_type(self, type_name: str, context_class: JavaClass) -> JavaClass | None:
        base_type = type_name.split("<")[0].strip()
        for import_def in context_class.imports:
            if import_def.class_name == base_type or import_def.is_wildcard:
                fqn = import_def.fully_qualified_name
                if import_def.is_wildcard:
                    fqn = f"{import_def.fully_qualified_name}.{base_type}"
                if fqn in self.analyzer.classes:
                    return self.analyzer.classes[fqn]
        potential_fqn = f"{context_class.package}.{base_type}"
        return self.analyzer.classes.get(potential_fqn)

    def resolve_class_type(self, type_name: str, context_class: JavaClass) -> tuple[str, str]:
        """
        Convenience method to resolve a type name to its base name and fully qualified name.
        Mimics the old JavaClass.resolve_class_type behavior.
        """
        base = type_name.split("<", 1)[0].strip()

        # Explicit imports
        for imp in context_class.imports or []:
            if not imp.is_wildcard and imp.class_name == base:
                return base, imp.fully_qualified_name

        # Wildcard imports (skip known JDK types)
        for imp in context_class.imports or []:
            if imp.is_wildcard and base not in JDK_TYPES:
                pkg = imp.fully_qualified_name
                return base, f"{pkg}.{base}"

        # Already a fully qualified name
        if "." in base:
            name = base.rsplit(".", 1)[-1]
            return name, base

        # Default to same package
        return base, f"{context_class.package}.{base}"
