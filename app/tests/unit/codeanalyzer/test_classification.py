"""
Unit tests for class classification logic.

Strategy: Pure unit tests with hand-created annotations and class names.
Real: Classification algorithms (annotation-driven and name-driven)
Mocked: Nothing (pure classification functions)

Test Responsibilities:
- Single function tests: Each test validates one classification scenario
  (annotation-driven vs name-driven patterns)
"""

import pytest

from app.src.codeanalyzer.classification import (
    infer_api_client_category,
    infer_class_category,
)
from app.src.codeanalyzer.models import (
    Annotation,
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaMethod,
    MemberVariable,
    MemberVariableCategory,
    Parameter,
)


def test_annotation_driven_controller():
    # Annotation should take precedence over name
    assert (
        infer_class_category("Foo", [Annotation(name="RestController")])
        == ClassCategory.CONTROLLER
    )


def test_annotation_driven_service():
    assert infer_class_category("Foo", [Annotation(name="Service")]) == ClassCategory.SERVICE


def test_annotation_driven_repository():
    assert infer_class_category("Foo", [Annotation(name="Repository")]) == ClassCategory.REPOSITORY


def test_annotation_driven_entity():
    assert infer_class_category("Foo", [Annotation(name="Entity")]) == ClassCategory.ENTITY


def test_name_driven_controller():
    assert infer_class_category("UserController", []) == ClassCategory.CONTROLLER


def test_name_driven_service():
    assert infer_class_category("OrderService", []) == ClassCategory.SERVICE


def test_name_driven_repository():
    assert infer_class_category("MyRepository", []) == ClassCategory.REPOSITORY


def test_name_driven_entity():
    assert infer_class_category("MyEntity", []) == ClassCategory.ENTITY


def test_unknown_category():
    assert infer_class_category("SomeRandomClass", []) == ClassCategory.OTHER


def test_priority_level_1_wins_over_level_3():
    """Level 1 (controller) should beat Level 3 (service) in substring matching."""
    # Use a name that has NO suffix matches, only substring matches
    assert infer_class_category("ControllerServiceHelper", []) == ClassCategory.CONTROLLER


def test_priority_level_2_wins_over_level_3():
    """Level 2 (repository) should beat Level 3 (service) in substring matching."""
    # Use a name that has NO suffix matches, only substring matches
    assert infer_class_category("RepositoryServiceHelper", []) == ClassCategory.REPOSITORY


def test_priority_level_1_wins_over_level_2():
    """Level 1 (controller) should beat Level 2 (repository) in substring matching."""
    # Use a name that has NO suffix matches, only substring matches
    assert infer_class_category("ControllerRepositoryHelper", []) == ClassCategory.CONTROLLER


def test_multiple_level_1_matches_raises_error():
    """Multiple Level 1 matches should raise ValueError."""
    # "test" and "controller" are both Level 1
    with pytest.raises(ValueError, match="Multiple category matches at priority level 1"):
        infer_class_category("TestControllerHelper", [])


def test_multiple_level_2_matches_raises_error():
    """Multiple Level 2 matches should raise ValueError."""
    # "dao" and "repository" are both Level 2
    with pytest.raises(ValueError, match="Multiple category matches at priority level 2"):
        infer_class_category("DaoRepositoryHelper", [])


def test_multiple_level_3_matches_raises_error():
    """Multiple Level 3 matches should raise ValueError."""
    # "service" and "svc" are both Level 3
    with pytest.raises(ValueError, match="Multiple category matches at priority level 3"):
        infer_class_category("ServiceSvcHelper", [])


def test_suffix_takes_precedence_over_priority():
    """Suffix matching should take precedence over substring priority levels."""
    # Ends with "service" (suffix match) even though "controller" is higher priority substring
    assert infer_class_category("ControllerService", []) == ClassCategory.SERVICE
    # Ends with "controller" (suffix match) even though has "service" substring
    assert infer_class_category("ServiceController", []) == ClassCategory.CONTROLLER


# ============================================================================
# API Client Detection Tests - Rule 1: Annotations
# ============================================================================


def test_api_client_feign_annotation():
    """Test detection via @FeignClient annotation."""
    annotations = [Annotation(name="FeignClient", values={"value": "user-service"})]
    result = infer_api_client_category("UserClient", annotations=annotations)
    assert result == ClassCategory.API_CLIENT


def test_api_client_rest_client_annotation():
    """Test detection via @RestClient annotation."""
    annotations = [Annotation(name="RestClient")]
    result = infer_api_client_category("PaymentClient", annotations=annotations)
    assert result == ClassCategory.API_CLIENT


def test_api_client_graphql_annotation():
    """Test detection via @GraphQLApi annotation."""
    annotations = [Annotation(name="GraphQLApi")]
    result = infer_api_client_category("GraphQLClient", annotations=annotations)
    assert result == ClassCategory.API_CLIENT


def test_api_client_web_service_annotation():
    """Test detection via @WebServiceClient annotation."""
    annotations = [Annotation(name="WebServiceClient")]
    result = infer_api_client_category("SoapClient", annotations=annotations)
    assert result == ClassCategory.API_CLIENT


def test_api_client_no_client_annotation():
    """Test that non-client annotations don't trigger detection."""
    annotations = [Annotation(name="Service"), Annotation(name="Component")]
    result = infer_api_client_category("RegularService", annotations=annotations)
    assert result is None


# ============================================================================
# API Client Detection Tests - Rule 2: Constructor Parameters
# ============================================================================


def test_api_client_constructor_rest_template():
    """Test detection via RestTemplate constructor parameter."""
    constructor = JavaMethod(
        name="UserApiClient",  # Constructor has same name as class
        return_type="",  # Constructors have no return type
        parameters=[
            Parameter(name="restTemplate", type="RestTemplate"),
            Parameter(name="baseUrl", type="String"),
        ],
    )

    result = infer_api_client_category("UserApiClient", methods=[constructor])
    assert result == ClassCategory.API_CLIENT


def test_api_client_constructor_fully_qualified_rest_template():
    """Test detection via fully qualified RestTemplate parameter."""
    constructor = JavaMethod(
        name="OrderClient",
        return_type="",
        parameters=[
            Parameter(name="template", type="org.springframework.web.client.RestTemplate")
        ],
    )

    result = infer_api_client_category("OrderClient", methods=[constructor])
    assert result == ClassCategory.API_CLIENT


def test_api_client_constructor_other_params():
    """Test that non-RestTemplate constructor params don't trigger detection."""
    constructor = JavaMethod(
        name="RegularService",
        return_type="",
        parameters=[
            Parameter(name="userRepository", type="UserRepository"),
            Parameter(name="config", type="Configuration"),
        ],
    )

    result = infer_api_client_category("RegularService", methods=[constructor])
    assert result is None


def test_api_client_regular_method_rest_template():
    """Test that RestTemplate in regular method (not constructor) doesn't trigger detection."""
    regular_method = JavaMethod(
        name="sendRequest",  # Different from class name
        return_type="String",
        parameters=[Parameter(name="restTemplate", type="RestTemplate")],
    )

    result = infer_api_client_category("ApiHelper", methods=[regular_method])
    assert result is None


# ============================================================================
# API Client Detection Tests - Rule 3: Member Variables
# ============================================================================


def test_api_client_member_okhttp():
    """Test detection via OkHttp client member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="httpClient",
            type="okhttp3.OkHttpClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("ApiWrapper", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_apache_http():
    """Test detection via Apache HttpClient member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="client",
            type="org.apache.http.client.HttpClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("HttpWrapper", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_java_http():
    """Test detection via Java 11+ HttpClient member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="httpClient",
            type="java.net.http.HttpClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("ModernHttpClient", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_graphql():
    """Test detection via GraphQL client member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="apolloClient",
            type="com.apollographql.apollo.ApolloClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("GraphQLService", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_grpc():
    """Test detection via gRPC client member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="channel",
            type="io.grpc.ManagedChannel",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("GrpcClient", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_thrift():
    """Test detection via Thrift client member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="thriftClient",
            type="org.apache.thrift.TServiceClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("ThriftWrapper", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_rest_template():
    """Test detection via RestTemplate member variable."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="restTemplate",
            type="org.springframework.web.client.RestTemplate",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("SpringApiClient", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_simple_name_match():
    """Test detection via simple class name when FQN not available."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="client",
            type="HttpClient",  # Simple name, not fully qualified
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category("SimpleClient", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_member_non_client_types():
    """Test that non-client member variables don't trigger detection."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="userService",
            type="UserService",
            category=MemberVariableCategory.CLASS_REFERENCE,
        ),
        ClassReferenceMemberVariable(
            name="repository",
            type="UserRepository",
            category=MemberVariableCategory.CLASS_REFERENCE,
        ),
        MemberVariable(name="count", type="int", category=MemberVariableCategory.PRIMITIVE),
    ]

    result = infer_api_client_category("RegularService", member_variables=member_vars)
    assert result is None


def test_api_client_member_primitive_variables():
    """Test that primitive member variables don't trigger detection."""
    member_vars = [
        MemberVariable(name="timeout", type="int", category=MemberVariableCategory.PRIMITIVE),
        MemberVariable(name="url", type="String", category=MemberVariableCategory.PRIMITIVE),
    ]

    result = infer_api_client_category("ConfigClass", member_variables=member_vars)
    assert result is None


# ============================================================================
# API Client Detection Tests - Integration & Edge Cases
# ============================================================================


def test_api_client_multiple_indicators():
    """Test detection with multiple positive indicators."""
    annotations = [Annotation(name="FeignClient")]
    member_vars = [
        ClassReferenceMemberVariable(
            name="httpClient",
            type="okhttp3.OkHttpClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]
    constructor = JavaMethod(
        name="MultiClient",
        return_type="",
        parameters=[Parameter(name="restTemplate", type="RestTemplate")],
    )

    result = infer_api_client_category(
        "MultiClient",
        annotations=annotations,
        member_variables=member_vars,
        methods=[constructor],
    )
    assert result == ClassCategory.API_CLIENT


def test_api_client_no_indicators():
    """Test that class with no API client indicators returns None."""
    annotations = [Annotation(name="Service")]
    member_vars = [
        ClassReferenceMemberVariable(
            name="userRepository",
            type="UserRepository",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]
    regular_method = JavaMethod(
        name="processUser",
        return_type="User",
        parameters=[Parameter(name="id", type="Long")],
    )

    result = infer_api_client_category(
        "UserService",
        annotations=annotations,
        member_variables=member_vars,
        methods=[regular_method],
    )
    assert result is None


def test_api_client_empty_inputs():
    """Test behavior with empty/None inputs."""
    result = infer_api_client_category("EmptyClass")
    assert result is None

    result = infer_api_client_category("EmptyClass", annotations=[])
    assert result is None

    result = infer_api_client_category("EmptyClass", member_variables=[])
    assert result is None

    result = infer_api_client_category("EmptyClass", methods=[])
    assert result is None


def test_api_client_mixed_member_variables():
    """Test with mix of client and non-client member variables."""
    member_vars = [
        MemberVariable(name="timeout", type="int", category=MemberVariableCategory.PRIMITIVE),
        ClassReferenceMemberVariable(
            name="userService",
            type="UserService",
            category=MemberVariableCategory.CLASS_REFERENCE,
        ),
        ClassReferenceMemberVariable(
            name="httpClient",  # This should trigger detection
            type="okhttp3.OkHttpClient",
            category=MemberVariableCategory.CLASS_REFERENCE,
        ),
        MemberVariable(name="config", type="Properties", category=MemberVariableCategory.OTHER),
    ]

    result = infer_api_client_category("MixedClass", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT


def test_api_client_annotation_priority():
    """Test that annotation detection works even with conflicting member variables."""
    annotations = [Annotation(name="FeignClient")]
    member_vars = [
        ClassReferenceMemberVariable(
            name="regularService",
            type="BusinessService",  # Non-client type
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]

    result = infer_api_client_category(
        "AnnotatedClient", annotations=annotations, member_variables=member_vars
    )
    assert result == ClassCategory.API_CLIENT


def test_api_client_constructor_resttemplate_explicit_and_wildcard():
    """Test detection via RestTemplate in constructor with explicit and wildcard imports."""
    # Parameter with explicit FQN import
    p1 = Parameter(name="t1", type="org.springframework.web.client.RestTemplate")
    # Parameter with simple name, assume wildcard import resolved via LocalNameResolver
    p2 = Parameter(name="t2", type="RestTemplate")
    p2.fqn_type = "org.springframework.web.client.RestTemplate"

    ctor = JavaMethod(
        name="MyApiClient",
        return_type="",
        parameters=[p1, p2],
    )

    result = infer_api_client_category("MyApiClient", methods=[ctor])
    assert result == ClassCategory.API_CLIENT


# ============================================================================
# Config override and additional annotation tests
# ============================================================================


def test_config_override_precedence():
    """Config override should take highest priority over annotations."""
    from app.src.codeanalyzer.code_analyzer_config import CodeAnalyzerConfig

    config = CodeAnalyzerConfig.from_json_string(
        '{"classification": {"class_name_overrides": {"MyClass": "repository"}}}'
    )
    result = infer_class_category(
        "MyClass",
        annotations=[Annotation(name="Service")],
        config=config,
    )
    assert result == ClassCategory.REPOSITORY


def test_annotation_mapper():
    assert infer_class_category("Foo", [Annotation(name="Mapper")]) == ClassCategory.MAPPER


def test_annotation_aspect():
    assert infer_class_category("Foo", [Annotation(name="Aspect")]) == ClassCategory.ASPECT


def test_annotation_dao():
    assert infer_class_category("Foo", [Annotation(name="Dao")]) == ClassCategory.DAO


def test_api_client_member_variable_fqn_type():
    """FQN type on a member variable triggers API client detection."""
    member_vars = [
        ClassReferenceMemberVariable(
            name="restTemplate",
            type="RestTemplate",
            fqn_type="org.springframework.web.client.RestTemplate",
            category=MemberVariableCategory.CLASS_REFERENCE,
        )
    ]
    result = infer_api_client_category("MyHelper", member_variables=member_vars)
    assert result == ClassCategory.API_CLIENT
