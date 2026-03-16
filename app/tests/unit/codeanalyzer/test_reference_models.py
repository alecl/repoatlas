"""
Unit tests for reference tracking model classes.

Strategy: Pure unit tests with hand-created reference objects.
Real: Reference state transitions, resolution status tracking
Mocked: Nothing (reference models are pure data structures)

Test Responsibilities:
- TestReferenceLocation: Reference location string representation
- TestResolutionAttempt: Resolution attempt tracking and status updates
- TestUnresolvedReference: Base unresolved reference behavior
- TestUnresolvedType: Type-specific unresolved reference behavior
- TestUnresolvedAutowire: Autowire-specific unresolved reference behavior
"""

from datetime import datetime

import pytest

from app.src.codeanalyzer.models import (
    ElementType,
    ReferenceLocation,
    ReferenceResolutionStatus,
    ReferenceScope,
    ResolutionAttempt,
    ResolvedLocation,
    UnresolvedAutowire,
    UnresolvedConstant,
    UnresolvedReference,
    UnresolvedType,
)


def test_reference_location_str():
    loc = ReferenceLocation(
        class_name="UserController",
        element_type=ElementType.CLASS_ANNOTATION,
        element_name="RequestMapping",
        detail="value",
    )
    assert str(loc) == "UserController.class_annotation.RequestMapping.value"


def test_resolution_attempt_and_status():
    ref = UnresolvedConstant(
        raw_value="Constants.BASE_PATH",
        location=ReferenceLocation(
            class_name="UserController",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    assert ref.resolution_status == ReferenceResolutionStatus.UNRESOLVED
    ref.add_resolution_attempt("local_constants", False, error_message="Not found")
    assert len(ref.resolution_attempts) == 1
    assert ref.resolution_attempts[0].strategy == "local_constants"
    assert not ref.resolution_attempts[0].success
    assert ref.resolution_attempts[0].error_message == "Not found"


def test_mark_partially_and_fully_resolved():
    ref = UnresolvedConstant(
        raw_value="Constants.BASE_PATH",
        location=ReferenceLocation(
            class_name="UserController",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    ref.mark_partially_resolved(ReferenceScope.SAME_JAR, class_name="Constants")
    assert ref.resolution_status == ReferenceResolutionStatus.PARTIALLY_RESOLVED
    assert ref.resolved_location.scope == ReferenceScope.SAME_JAR
    assert ref.resolved_location.class_name == "Constants"

    resolved_loc = ResolvedLocation(scope=ReferenceScope.SAME_JAR, class_name="Constants")
    ref.mark_fully_resolved("/api/v1", resolved_loc)
    assert ref.resolution_status == ReferenceResolutionStatus.FULLY_RESOLVED
    assert ref.resolved_value == "/api/v1"
    assert ref.resolved_location == resolved_loc


def test_mark_unresolvable():
    ref = UnresolvedConstant(
        raw_value="Constants.BASE_PATH",
        location=ReferenceLocation(
            class_name="UserController",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    ref.mark_unresolvable("Could not resolve constant")
    assert ref.resolution_status == ReferenceResolutionStatus.UNRESOLVABLE
    assert ref.resolution_attempts[-1].error_message == "Could not resolve constant"


def test_unresolved_type_and_autowire_fields():
    t = UnresolvedType(
        raw_value="SomeType",
        location=ReferenceLocation(
            class_name="SomeClass",
            element_type=ElementType.FIELD_DECLARATION,
            element_name="someField",
        ),
        is_interface=True,
        is_generic=False,
    )
    assert t.is_interface
    assert not t.is_generic

    a = UnresolvedAutowire(
        raw_value="SomeService",
        location=ReferenceLocation(
            class_name="SomeClass",
            element_type=ElementType.FIELD_DECLARATION,
            element_name="someService",
        ),
        interface_type="SomeService",
        qualifier="special",
    )
    assert a.interface_type == "SomeService"
    assert a.qualifier == "special"
