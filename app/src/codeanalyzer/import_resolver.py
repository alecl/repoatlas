from typing import Any, Dict, Optional, Set

from .models import ImportDefinition, JavaClass, ReferenceScope, ResolvedLocation


class ImportResolver:
    """
    Lazily resolves import statements to determine their location and scope.

    Responsibilities:
    - Resolve imports only when needed by other resolvers
    - Cache resolved import locations for performance
    - Track which imports are actually used vs unused
    - Determine scope (JDK, same JAR, different JAR, third-party)
    """

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self._import_cache: dict[str, ResolvedLocation | None] = {}
        self._used_imports: set[str] = set()

    def resolve_import_for_type(
        self, type_name: str, context_class: JavaClass
    ) -> ResolvedLocation | None:
        """Resolve an import only when needed by other resolvers."""
        for import_def in context_class.imports:
            if self._import_matches_type(import_def, type_name):
                return self._resolve_import_lazy(import_def, context_class)
        return None

    def resolve_used_imports(self) -> bool:
        """Post-processing pass to resolve all imports that were actually used."""
        # This is called as part of the resolution pipeline
        # It doesn't resolve anything eagerly, just returns False
        # The actual resolution happens lazily via resolve_import_for_type
        return False

    def _import_matches_type(self, import_def: ImportDefinition, type_name: str) -> bool:
        if import_def.is_wildcard:
            return True  # Wildcard imports may match any type in the package
        return import_def.class_name == type_name

    def _resolve_import_lazy(
        self, import_def: ImportDefinition, context_class: JavaClass
    ) -> ResolvedLocation | None:
        fqn = import_def.fully_qualified_name
        if fqn in self._import_cache:
            return self._import_cache[fqn]
        self._used_imports.add(fqn)
        location = self._determine_import_location(fqn, context_class)
        self._import_cache[fqn] = location
        return location

    def _determine_import_location(
        self, fqn: str, context_class: JavaClass
    ) -> ResolvedLocation | None:
        if fqn.startswith("java.") or fqn.startswith("javax."):
            return ResolvedLocation(scope=ReferenceScope.JDK, package_name=fqn)
        for class_fqn, java_class in self.analyzer.classes.items():
            if class_fqn == fqn or (fqn.endswith(".*") and class_fqn.startswith(fqn[:-2])):
                return ResolvedLocation(
                    scope=self._determine_scope_from_path(java_class, context_class),
                    class_name=java_class.name,
                    package_name=java_class.package,
                    jar_name=None,
                )
        return ResolvedLocation(scope=ReferenceScope.THIRD_PARTY, package_name=fqn)

    def _determine_scope_from_path(
        self, target_class: JavaClass, context_class: JavaClass
    ) -> ReferenceScope:
        """
        Determine scope based on package for user code.
        Same package => same jar; different package => same repo, different jar.
        """
        if target_class.package == context_class.package or target_class.package.startswith(
            context_class.package + "."
        ):
            return ReferenceScope.SAME_JAR
        return ReferenceScope.SAME_REPO_DIFFERENT_JAR

    def get_import_statistics(self) -> dict[str, Any]:
        return {
            "total_imports": len(self._import_cache),
            "used_imports": len(self._used_imports),
            "unused_imports": len(self._import_cache) - len(self._used_imports),
        }
