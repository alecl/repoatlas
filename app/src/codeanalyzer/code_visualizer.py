import json
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaClass,
    MethodCallInfo,
    RestControllerClass,
    RestEndpoint,
    ServiceClass,
)

service_methods_only = True


class CodeVisualizer:
    """
    Class for visualizing Java code analysis results in various formats.
    """

    @staticmethod
    def format_text(classes: list[JavaClass]) -> str:
        """
        Format analysis results as plain text.

        Args:
            classes: List of JavaClass objects to format

        Returns:
            Formatted text output
        """
        output = []

        # Classes summary
        output.append("=== Java Classes ===")
        output.append(f"Total classes: {len(classes)}")

        for category in ClassCategory:
            count = len([cls for cls in classes if cls.category == category])
            if count > 0:
                output.append(f"  {category.value}: {count}")

        output.append("")

        # Controllers
        controllers = [
            cls
            for cls in classes
            if cls.category == ClassCategory.CONTROLLER and isinstance(cls, RestControllerClass)
        ]
        if controllers:
            output.append("=== Controllers ===")
            for controller in controllers:
                output.append(f"Controller: {controller.name}")
                output.append(f"  Package: {controller.package}")
                output.append(f"  File Path: {controller.relative_path}")
                output.append(f"  Base path: {controller.base_endpoint_path}")

                # Print endpoints
                endpoints = controller.get_all_endpoints()
                if endpoints:
                    output.append("  Endpoints:")
                    for http_method, paths in endpoints.items():
                        for path, method_name in paths:
                            output.append(f"    {http_method}: {path} -> {method_name}")

                # Print service dependencies
                if controller.service_variables:
                    output.append("  Service Dependencies:")
                    for service in controller.service_variables:
                        qualifier_info = (
                            f" (qualifier: {service.qualifier})" if service.qualifier else ""
                        )
                        output.append(f"    {service.type} {service.name}{qualifier_info}")

                # Print service method calls
                for method in controller.methods:
                    if method.method_calls:
                        output.append(f"  Method {method.name} calls:")

                        for call in method.method_calls:
                            service_impl = ""
                            if (
                                hasattr(call, "source_variable")
                                and call.source_variable is not None
                                and hasattr(call.source_variable, "resolved_implementation")
                                and call.source_variable.resolved_implementation is not None
                                and hasattr(call.source_variable.resolved_implementation, "name")
                            ):
                                service_impl = (
                                    f" -> {call.source_variable.resolved_implementation.name}"
                                )
                            output.append(
                                f"    ({call.target_type}{service_impl}){call.target_name}.{call.method_name}()"
                            )

                output.append("")

        # Services
        services = [
            cls
            for cls in classes
            if cls.category == ClassCategory.SERVICE and isinstance(cls, ServiceClass)
        ]
        if services:
            output.append("=== Services ===")
            for service in services:
                output.append(f"Service: {service.name}")
                output.append(f"  Package: {service.package}")
                output.append(f"  File Path: {service.relative_path}")

                # Print methods
                if service.methods:
                    output.append("  Methods:")
                    for method in service.methods:
                        # TODO: This type is the AST type, not the Java type. We will eventually map to the method declaration to get the real types.
                        # params = ", ".join(
                        #     [f"{p.type} {p.name}" for p in method.parameters]
                        # )
                        params = ", ".join([f"{p.name}" for p in method.parameters])
                        # TODO: This type is the AST type, not the Java type. We will eventually map to the method declaration to get the real types.
                        # output.append(
                        #     f"    {method.return_type} {method.name}({params})"
                        # )
                        output.append(f"    {method.name}({params})")

                output.append("")

        return "\n".join(output)

    @staticmethod
    def format_json(classes: list[JavaClass]) -> str:
        """
        Format analysis results as JSON.

        Args:
            classes: List of JavaClass objects to format

        Returns:
            JSON string output
        """
        # Build a result dictionary
        controllers = [
            cls
            for cls in classes
            if cls.category == ClassCategory.CONTROLLER and isinstance(cls, RestControllerClass)
        ]
        services = [
            cls
            for cls in classes
            if cls.category == ClassCategory.SERVICE and isinstance(cls, ServiceClass)
        ]

        result = {
            "summary": {
                "total_classes": len(classes),
                "controllers": len(controllers),
                "services": len(services),
            },
            "controllers": [],
            "services": [],
        }

        # Add controllers
        for controller in controllers:
            controller_data = {
                "name": controller.name,
                "package": controller.package,
                "fully_qualified_name": controller.fully_qualified_name,
                "base_endpoint_path": controller.base_endpoint_path,
                "endpoints": {},
                "service_dependencies": [],
                "method_calls": {},
            }

            # Add endpoints
            endpoints = controller.get_all_endpoints()
            for http_method, paths in endpoints.items():
                controller_data["endpoints"][http_method] = [
                    {"path": path, "method": method_name} for path, method_name in paths
                ]

            # Add service dependencies
            for service in controller.service_variables:
                controller_data["service_dependencies"].append(
                    {
                        "name": service.name,
                        "type": service.type,
                        "is_autowired": service.is_autowired,
                        "qualifier": service.qualifier,
                    }
                )

            # Add method calls
            for method in controller.methods:
                if service_methods_only:
                    if not method.has_service_calls():
                        continue
                    calls = method.get_service_calls()
                else:
                    if not method.method_calls:
                        continue
                    calls = method.method_calls
                controller_data["method_calls"][method.name] = [
                    {
                        "service_name": call.target_name,
                        "method_name": call.method_name,
                        "service_type": call.target_type,
                        "arguments": [
                            {
                                "type": arg.expression_type.value,
                                "raw_expression": arg.raw_expression,
                            }
                            for arg in call.arguments
                        ],
                    }
                    for call in calls
                ]

            result["controllers"].append(controller_data)

        # Add services
        for service in services:
            service_data = {
                "name": service.name,
                "package": service.package,
                "fully_qualified_name": service.fully_qualified_name,
                "methods": [],
            }

            # Add methods
            for method in service.methods:
                service_data["methods"].append(
                    {
                        "name": method.name,
                        "return_type": method.return_type,
                        "parameters": [
                            {"name": p.name, "type": p.type} for p in method.parameters
                        ],
                    }
                )

            result["services"].append(service_data)

        return json.dumps(result, indent=2)

    @staticmethod
    def format_markdown(classes: list[JavaClass]) -> str:
        """
        Format analysis results as Markdown.

        Args:
            classes: List of JavaClass objects to format

        Returns:
            Markdown string output
        """
        output = []

        # Title
        output.append("# Java Spring Analysis Results")
        output.append("")

        # Summary
        output.append("## Summary")
        output.append("")
        output.append(f"**Total classes**: {len(classes)}")

        categories = []
        for category in ClassCategory:
            count = len([cls for cls in classes if cls.category == category])
            if count > 0:
                categories.append(f"**{category.value}**: {count}")

                # Print class names for API_CLIENT category
                if category == ClassCategory.API_CLIENT:
                    api_clients = [
                        cls.fully_qualified_name
                        for cls in classes
                        if cls.category == ClassCategory.API_CLIENT
                    ]
                    output.append("\n**API Client Classes:**")
                    for client in api_clients:
                        output.append(f"- {client}")
                        output.append("")
        # TODO: Add trace of how we identified API clients
        output.append(", ".join(categories))
        output.append("")

        # Controllers
        controllers = [
            cls
            for cls in classes
            if cls.category == ClassCategory.CONTROLLER and isinstance(cls, RestControllerClass)
        ]
        if controllers:
            output.append("## Controllers")
            output.append("")

            for controller in controllers:
                output.append(f"### {controller.name}")
                output.append("")
                output.append(f"- **Package**: `{controller.package}`")
                output.append(f"- **File Path**: `{controller.relative_path}`")
                output.append(f"- **Base Endpoint Path**: `{controller.base_endpoint_path}`")
                output.append("")

                # Endpoints table
                endpoints = controller.get_all_endpoints()
                if endpoints:
                    output.append("#### Endpoints")
                    output.append("")
                    output.append("| HTTP Method | Path | Method |")
                    output.append("|------------|------|--------|")

                    for http_method, paths in endpoints.items():
                        for path, method_name in paths:
                            output.append(f"| {http_method} | `{path}` | `{method_name}` |")

                    output.append("")

                # Service dependencies
                if controller.service_variables:
                    output.append("#### Service Dependencies")
                    output.append("")
                    output.append("| Type | Superclass | Name | Qualifier |")
                    output.append("|------|------------|------|-----------|")

                    for service in controller.service_variables:
                        qualifier = service.qualifier if service.qualifier else ""
                        # If resolved_implementation is present, show superclass/type split
                        resolved_impl = getattr(service, "resolved_implementation", None)
                        if resolved_impl and getattr(resolved_impl, "name", None):
                            superclass = service.type
                            type_col = resolved_impl.name
                        else:
                            superclass = ""
                            type_col = service.type
                        output.append(
                            f"| `{type_col}` | `{superclass}` | `{service.name}` | {qualifier} |"
                        )

                    output.append("")

                # Service method calls
                if service_methods_only:
                    has_method_calls = any(
                        method.has_service_calls() for method in controller.methods
                    )
                else:
                    has_method_calls = any(method.method_calls for method in controller.methods)
                if has_method_calls:
                    output.append("#### Service Method Calls")
                    output.append("")
                    output.append("| Controller Method | Service | Service Method | Args |")
                    output.append("|-------------------|---------|----------------|------|")

                    for method in controller.methods:
                        if service_methods_only:
                            if not method.has_service_calls():
                                continue
                            calls = method.get_service_calls()
                        else:
                            if not method.method_calls:
                                continue
                            calls = method.method_calls
                        for call in calls:
                            # TODO: This type is the AST type, not the Java type. We will eventually map to the method declaration to get the real types.
                            # args_list = ", ".join(
                            #     f"{arg.expression_type.value} {arg.raw_expression}"
                            #     for arg in call.arguments
                            # )
                            args_list = ", ".join(
                                f"{arg.raw_expression}" for arg in call.arguments
                            )
                            output.append(
                                f"| `{method.name}` | `{call.target_name}` | `{call.method_name}` | {args_list} |"
                            )

                    output.append("")

        # Services
        services = [
            cls
            for cls in classes
            if cls.category == ClassCategory.SERVICE and isinstance(cls, ServiceClass)
        ]
        if services:
            output.append("## Services")
            output.append("")

            for service in services:
                output.append(f"### {service.name}")
                output.append("")
                output.append(f"- **Package**: `{service.package}`")
                output.append(f"- **File Path**: `{service.relative_path}`")
                output.append(f"- **Fully Qualified Name**: `{service.fully_qualified_name}`")
                output.append("")

                # Methods table
                if service.methods:
                    output.append("#### Methods")
                    output.append("")
                    output.append("| Return Type | Method | Parameters |")
                    output.append("|-------------|--------|------------|")

                    for method in service.methods:
                        params = ", ".join([f"{p.type} {p.name}" for p in method.parameters])
                        output.append(f"| `{method.return_type}` | `{method.name}` | {params} |")

                    output.append("")

        return "\n".join(output)

    @staticmethod
    def format_mermaid_classdiagram(classes: list[JavaClass]) -> str:
        """
        Format class relationships as a Mermaid class diagram.

        Args:
            classes: List of JavaClass objects to format

        Returns:
            Mermaid class diagram string
        """
        output = []

        # Start class diagram
        output.append("```mermaid")
        output.append("classDiagram")

        # Add classes
        for cls in classes:
            # Skip non-controller/service classes to keep diagram clean
            if cls.category not in [ClassCategory.CONTROLLER, ClassCategory.SERVICE]:
                continue

            # Add class with category annotation
            output.append(f"  class {cls.name} {{")
            output.append(f"    <<{cls.category.value}>>")

            # Add methods
            for method in cls.methods:
                # For controllers, only include REST endpoints
                if cls.category == ClassCategory.CONTROLLER and not isinstance(
                    method, RestEndpoint
                ):
                    continue

                params = ", ".join([f"{p.type} {p.name}" for p in method.parameters])
                output.append(f"    +{method.return_type} {method.name}({params})")

            output.append("  }")

        # Add relationships
        for controller in [cls for cls in classes if cls.category == ClassCategory.CONTROLLER]:
            for service_var in controller.get_class_references():
                if service_var.referenced_class_category == ClassCategory.SERVICE:
                    # If resolved_implementation is present, show superclass relationship
                    resolved_impl = getattr(service_var, "resolved_implementation", None)
                    if resolved_impl and getattr(resolved_impl, "name", None):
                        # Draw: Controller --> ResolvedImpl : uses
                        output.append(f"  {controller.name} --> {resolved_impl.name} : uses")
                        # Draw: ResolvedImpl <|-- ServiceType : subclass
                        output.append(f"  {resolved_impl.name} <|-- {service_var.type} : subclass")
                    else:
                        output.append(f"  {controller.name} --> {service_var.type} : uses")

        # Close diagram
        output.append("```")

        return "\n".join(output)

    @staticmethod
    def format_mermaid_flowchart(classes: list[JavaClass]) -> str:
        """
        Format controller-service flow as a Mermaid flowchart.

        Args:
            classes: List of JavaClass objects to format

        Returns:
            Mermaid flowchart string
        """
        output = []

        # Start flowchart
        output.append("```mermaid")
        output.append("flowchart TD")

        # Add controllers as rectangles
        controllers = [
            cls
            for cls in classes
            if cls.category == ClassCategory.CONTROLLER and isinstance(cls, RestControllerClass)
        ]

        for controller in controllers:
            output.append(f'  {controller.name}["Controller: {controller.name}"]')

            # Add endpoints as rounded rectangles
            for method in controller.methods:
                if isinstance(method, RestEndpoint):
                    # Generate a unique ID for the method
                    method_id = f"{controller.name}_{method.name}"

                    # Get HTTP methods
                    http_methods = list(method.path_mappings.keys())
                    http_str = "/".join(http_methods)

                    output.append(f'  {method_id}("{http_str}: {method.name}")')
                    output.append(f"  {controller.name} --> {method_id}")

                    # Add service method calls
                    for call in method.method_calls:
                        # Check for resolved implementation
                        resolved_impl = (
                            getattr(call.source_variable, "resolved_implementation", None)
                            if hasattr(call, "source_variable")
                            and call.source_variable is not None
                            else None
                        )
                        if resolved_impl and getattr(resolved_impl, "name", None):
                            call_id = f"{resolved_impl.name}_{call.method_name}"
                            # Mermaid supports <br/> for line breaks in HTML labels
                            output.append(
                                f'  {call_id}["Service: {resolved_impl.name}<br/>subclass of: {call.target_type}.{call.method_name}"]'
                            )
                        else:
                            call_id = f"{call.target_type}_{call.method_name}"
                            output.append(
                                f'  {call_id}["Service: {call.target_type}.{call.method_name}"]'
                            )
                        output.append(f"  {method_id} --> {call_id}")

        # Close flowchart
        output.append("```")

        return "\n".join(output)
