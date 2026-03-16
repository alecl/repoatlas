from typing import Dict

from .models import RestControllerClass, RestEndpoint


class PathResolver:
    """
    Resolves REST endpoint paths, including constant references.
    """

    def __init__(self, analyzer):
        self.analyzer = analyzer
        # Allow tests to pass a fake analyzer without constant_resolver
        self.constant_resolver = getattr(analyzer, "constant_resolver", None)

    def resolve_all(self) -> bool:
        """Resolve all paths in REST endpoints."""
        changes_made = False
        for controller in self._get_all_controllers():
            # base_path = controller.base_endpoint_path  # F841: assigned but never used
            for endpoint in controller.endpoints:
                for method, path in endpoint.path_mappings.items():
                    if self._looks_like_constant_reference(path) and self.constant_resolver:
                        resolved_path = self.constant_resolver._resolve_constant_chain(
                            unresolved=type(
                                "FakeUnresolved",
                                (),
                                {
                                    "raw_value": path,
                                    "add_resolution_attempt": lambda *a, **k: None,
                                },
                            )(),
                            context_class=controller,
                        )
                        if resolved_path and resolved_path != path:
                            endpoint.path_mappings[method] = resolved_path
                            changes_made = True
        return changes_made

    def _get_all_controllers(self):
        return [cls for cls in self.analyzer.classes.values() if hasattr(cls, "endpoints")]

    def _looks_like_constant_reference(self, value: str) -> bool:
        if not isinstance(value, str):
            return False
        value = value.strip()
        return bool(
            "." in value
            and not value.startswith(("/", '"', "'"))
            and value.lower() not in ("true", "false")
        )
