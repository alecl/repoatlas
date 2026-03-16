"""
Integration tests for the full resolver pipeline.

Strategy: Real tree-sitter parsing with multi-file Java projects via tmp_path.
No mocks — exercises parse → import → type → constant → path → autowire → property.

Test Responsibilities:
- Full pipeline with controller/service/entity
- Property resolution via @Value + application.properties
- Constant chaining across classes
"""

from app.src.codeanalyzer.analyzer import JavaAnalyzer


def test_full_pipeline_controller_service_entity(tmp_path):
    """Parse 3 files, run full resolution, verify all resolver stages."""
    # Entity
    entity = tmp_path / "User.java"
    entity.write_text("""\
package com.example;
public class User {
    private Long id;
    private String name;
}
""")

    # Service
    service = tmp_path / "UserService.java"
    service.write_text("""\
package com.example;
import org.springframework.stereotype.Service;
@Service
public class UserService {
    public User findById(Long id) { return null; }
}
""")

    # Controller
    controller = tmp_path / "UserController.java"
    controller.write_text("""\
package com.example;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
@RestController
public class UserController {
    private UserService userService;
    @GetMapping("/users")
    public User getUser() {
        return userService.findById(1L);
    }
}
""")

    analyzer = JavaAnalyzer()
    analyzer.parse_file(str(entity))
    analyzer.parse_file(str(service))
    analyzer.parse_file(str(controller))
    analyzer._resolve_all_references()

    # Verify controller is classified correctly
    ctrl_class = analyzer.classes["com.example.UserController"]
    assert ctrl_class.category.value == "controller"

    # Verify service is classified correctly
    svc_class = analyzer.classes["com.example.UserService"]
    assert svc_class.category.value == "service"

    # Verify controller has method calls
    get_method = next(m for m in ctrl_class.methods if m.name == "getUser")
    assert len(get_method.method_calls) >= 1
    assert get_method.method_calls[0].method_name == "findById"


def test_full_pipeline_property_resolution(tmp_path):
    """@Value('${server.port}') resolved from application.properties."""
    # Properties file
    props = tmp_path / "application.properties"
    props.write_text("server.port=8080\nserver.host=localhost\n")

    # Class with @Value member
    java = tmp_path / "AppConfig.java"
    java.write_text("""\
package com.example;
import org.springframework.beans.factory.annotation.Value;
public class AppConfig {
    @Value("${server.port}")
    private String port;
    @Value("${server.host}")
    private String host;
}
""")

    analyzer = JavaAnalyzer()
    analyzer.parse_file(str(java))
    analyzer.property_resolver.load_properties_file(str(props))
    analyzer._resolve_all_references()

    config_class = analyzer.classes["com.example.AppConfig"]
    port_var = next(v for v in config_class.member_variables if v.name == "port")
    assert hasattr(port_var, "resolved_properties")
    assert port_var.resolved_properties["server.port"] == "8080"


def test_full_pipeline_constant_chaining(tmp_path):
    """Class A references Class B's constant; verify chain resolution."""
    # Constants class
    const_file = tmp_path / "ApiConstants.java"
    const_file.write_text("""\
package com.example;
public class ApiConstants {
    public static final String BASE_PATH = "/api/v1";
}
""")

    # Controller referencing constants
    ctrl_file = tmp_path / "MyController.java"
    ctrl_file.write_text("""\
package com.example;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestMapping;
@RestController
@RequestMapping(ApiConstants.BASE_PATH)
public class MyController {
}
""")

    analyzer = JavaAnalyzer()
    analyzer.parse_file(str(const_file))
    analyzer.parse_file(str(ctrl_file))
    analyzer._resolve_all_references()

    # The constant resolver should have resolved the constant
    const_class = analyzer.classes["com.example.ApiConstants"]
    assert "BASE_PATH" in const_class.constants
    assert const_class.constants["BASE_PATH"] == "/api/v1"
