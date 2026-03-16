from .models import MemberVariable


class PropertyReference:
    def __init__(self, name: str, default_value: str | None = None):
        self.name = name
        self.default_value = default_value


class PropertyResolver:
    """
    Resolves Spring property references in @Value annotations.

    Limitation: This resolver only looks up properties from explicitly loaded
    .properties files. Environment variable fallbacks (which Spring supports
    at runtime) are not simulated, as the analyzer cannot know the target
    project's runtime environment.
    """

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.properties: dict[str, dict[str, str]] = {}

    def load_properties_file(self, file_path: str):
        properties = self._parse_properties_file(file_path)
        self.properties[file_path] = properties

    def resolve_all(self) -> bool:
        changes_made = False
        for java_class in self.analyzer.classes.values():
            for member in java_class.member_variables:
                changes_made |= self._resolve_member_value(member)
            for method in java_class.methods:
                for param in getattr(method, "parameters", []):
                    changes_made |= self._resolve_parameter_value(param)
        return changes_made

    def _resolve_member_value(self, member: MemberVariable) -> bool:
        for annotation in getattr(member, "annotations", []):
            if annotation.name == "Value" and annotation.value:
                property_ref = self._parse_property_reference(annotation.value)
                if property_ref:
                    resolved_value = self._lookup_property(property_ref)
                    if resolved_value:
                        # Use __dict__ to allow dynamic attribute for test models
                        if not hasattr(member, "resolved_properties"):
                            try:
                                member.resolved_properties = {}
                            except Exception:
                                # Fallback for pydantic models
                                object.__setattr__(member, "resolved_properties", {})
                        member.resolved_properties[property_ref.name] = resolved_value
                        return True
        return False

    def _resolve_parameter_value(self, param) -> bool:
        for annotation in getattr(param, "annotations", []):
            if annotation.name == "Value" and annotation.value:
                property_ref = self._parse_property_reference(annotation.value)
                if property_ref:
                    resolved_value = self._lookup_property(property_ref)
                    if resolved_value:
                        if not hasattr(param, "resolved_properties"):
                            try:
                                param.resolved_properties = {}
                            except Exception:
                                param.__dict__["resolved_properties"] = {}
                        param.resolved_properties[property_ref.name] = resolved_value
                        return True
        return False

    def _parse_property_reference(self, value: str) -> PropertyReference | None:
        if not value.startswith("${") or not value.endswith("}"):
            return None
        content = value[2:-1]
        parts = content.split(":", 1)
        property_name = parts[0]
        default_value = parts[1] if len(parts) > 1 else None
        return PropertyReference(name=property_name, default_value=default_value)

    def _lookup_property(self, property_ref: PropertyReference) -> str | None:
        for file_path in sorted(self.properties.keys(), reverse=True):
            if property_ref.name in self.properties[file_path]:
                return self.properties[file_path][property_ref.name]
        return property_ref.default_value

    def _parse_properties_file(self, file_path: str) -> dict[str, str]:
        properties = {}
        try:
            with open(file_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        properties[key.strip()] = value.strip()
        except Exception:
            pass
        return properties
