# Design Philosophy: Code Relationship Mapping via Syntax Analysis

## Core Approach

Our tool takes a fundamentally different approach to mapping relationships between software components. Rather than relying on runtime instrumentation (like OpenTelemetry) or compilation artifacts, we're using syntax parsing through TreeSitter to analyze code directly at the source level. This allows us to identify connections between services, repositories, and components without the overhead of building or running the systems.

## Key Benefits

### Speed and Accessibility

By analyzing source code directly, we eliminate the time-consuming process of setting up build environments, resolving dependencies, and waiting for compilation. This dramatically accelerates the initial analysis phase, allowing teams to quickly understand system relationships without the typical setup costs.

### Reduced Dependencies

Traditional approaches often require intimate knowledge of build systems (Maven, Gradle, webpack), runtime environments, and deployment configurations. Our syntax-first approach removes these dependencies, making the tool accessible to engineers regardless of their familiarity with specific build ecosystems.

### Incremental and Partial Analysis

The ability to analyze individual files or snippets enables incremental mapping of system relationships. Teams can start small, focusing on critical components, and gradually expand their understanding. This incremental approach provides immediate value without requiring a comprehensive analysis of the entire codebase upfront.

### Technology Agnosticism

By focusing on language syntax rather than framework-specific compilation or runtime behavior, we can support diverse technology stacks. Whether it's Spring controllers in Java, Express routes in Node.js, or FastAPI endpoints in Python, the parser-based approach can identify and map relationships across technological boundaries.

## Advanced Analysis Capabilities

### Dependency Injection Resolution

Even at a static analysis level, we can resolve dependency injection patterns to understand how classes are wired together. This gives us insight into actual runtime relationships without requiring the application to be running.

### Orphaned Code Identification

The system can generate reports of potentially unused or orphaned code. This provides valuable insights for refactoring efforts and technical debt reduction. When code appears orphaned, it serves as a trigger for further investigation – is it truly dead code or are we missing a connection pattern?

## Addressing Limitations

### Mitigating False Positives

The issue of mapping code that is never executed can be significantly reduced by properly identifying all inbound systems that call into a component. There will still be edge cases triggered by cron jobs, event handlers, or human intervention, but these can be specifically noted and incorporated into the analysis with appropriate tagging.

### Dynamic Language Features

Languages with reflection capabilities (Java, Ruby) or highly dynamic aspects (JavaScript, Python) present challenges for static analysis. These may lead to missed connections or behaviors. For critical systems where these gaps are significant:

- Future expansions could include integrating with profilers during automated test runs
- Capturing OpenTelemetry spans/traces from production systems to supplement static analysis
- Adding specific heuristics for common reflection patterns

These would not be starting points for analysis but rather targeted enhancements when specific limitations are identified.

### External Configuration and Infrastructure

Several aspects outside the code itself can influence system behavior and connections:

- Secret management systems in Kubernetes or AWS
- Command-line parameter sequences
- Configuration files with critical information like URLs or base paths
- Infrastructure elements like load balancers with path-based routing

Initially, we'll distill these on an as-needed basis into mappings or context rather than attempting to provide direct support for all possibilities. A plugin architecture may evolve to allow direct integration with these systems as the tool matures.

Integration with CI/CD pipelines presents a compelling opportunity, as these systems already have the necessary access and permissions to retrieve this information. This could include analysis of compiled artifacts alongside the source analysis, offering a more complete picture.

## Use Cases

Our approach enables several powerful capabilities:

1. **Impact Analysis**: Quickly identify which systems might be affected by a proposed change
2. **Dependency Mapping**: Trace library usage across the organization for upgrade planning
3. **API Consumer Identification**: Determine which services call specific APIs for deprecation planning
4. **MVC Pattern Recognition**: Map controllers to their respective models and views
5. **Cross-Service Request Flows**: Visualize how requests flow between different services

## Future Enhancement Path

Our syntax-first approach provides a solid foundation while allowing for progressive enhancement:

1. **Schema Integration**: Incorporating OpenAPI/Swagger specs and GraphQL schemas to validate and enhance our findings
2. **Artifact Analysis**: Adding built artifact inspection where convenient (e.g., from existing CI pipelines)
3. **Runtime Data**: Eventually incorporating runtime telemetry data to validate static analysis findings
4. **Dynamic Analysis**: Adding targeted profiling for systems with heavy use of reflection or dynamic code loading
5. **Configuration Analysis**: Adding plugins to parse and incorporate external configuration sources
6. **Infrastructure Mapping**: Integrating with infrastructure-as-code repositories to understand routing and connectivity

This approach allows us to deliver immediate value while establishing a framework that can incorporate additional data sources as they become available or necessary.

By starting with syntax analysis, we create a powerful tool that balances immediate utility with future extensibility, making system relationships visible without the traditional costs of comprehensive instrumentation or compilation-based analysis.
