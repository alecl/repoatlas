import pytest

from app.src.codeanalyzer.models import ImportDefinition
from app.src.codeanalyzer.parser import LocalNameResolver


class TestLocalNameResolver:
    @pytest.mark.parametrize(
        "simple_name,fqn",
        [
            ("String", "java.lang.String"),
            ("Integer", "java.lang.Integer"),
            ("Boolean", "java.lang.Boolean"),
        ],
    )
    def test_java_lang_fallback(self, simple_name, fqn):
        resolver = LocalNameResolver("com.example", [])
        assert resolver.to_fqn(simple_name) == fqn

    def test_explicit_import(self):
        imports = [ImportDefinition(fully_qualified_name="com.example.FooService")]
        resolver = LocalNameResolver("com.test", imports)
        assert resolver.to_fqn("FooService") == "com.example.FooService"

    def test_wildcard_import(self):
        imports = [ImportDefinition(fully_qualified_name="org.example.service", is_wildcard=True)]
        resolver = LocalNameResolver("com.test", imports)
        assert resolver.to_fqn("BarService") == "org.example.service.BarService"

    def test_generics_stripped(self):
        imports = [ImportDefinition(fully_qualified_name="com.example.GenericClass")]
        resolver = LocalNameResolver("com.test", imports)
        assert resolver.to_fqn("GenericClass<String>") == "com.example.GenericClass"

    def test_no_import_simple_name(self):
        resolver = LocalNameResolver("com.test", [])
        assert resolver.to_fqn("UnknownType") == "UnknownType"
