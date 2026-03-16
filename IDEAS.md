# IDEAS.md

Contributing ideas for RepoAtlas — a static analyzer that extracts structure and relationships from Java Spring applications using tree-sitter.

All ideas below stay within scope: **syntax-first, static extraction of code structure and relationships for LLM context generation.** No runtime instrumentation, no security scanning, no code-smell detection.

---

## 1. Language & Framework Support

### Why Java First

RepoAtlas started with Java because Java is uniquely hard to analyze file-by-file. Dependency injection, annotation-driven wiring (`@Autowired`, `@RestController`, `@Transactional`), SpEL expressions, and deeply layered enterprise conventions mean that reading a single file in isolation tells you almost nothing about what it does or what it connects to. The whole point of RepoAtlas is to reconstruct those invisible relationships statically — and Java Spring is where that problem is most acute.

### Expanding Java Framework Coverage

**Current state:** Spring MVC REST controllers.

- **Spring WebFlux** — Reactive endpoints with `Mono`/`Flux` return types
- **JAX-RS / Jersey** — Standard Java REST API annotations (`@Path`, `@GET`, etc.)
- **Quarkus** — Compile-time DI and REST annotations
- **Micronaut** — Lightweight AOP-based controllers

### API Protocols Beyond REST

- **GraphQL** — Schema parsing, resolver-to-service mapping
- **gRPC** — Protobuf service definitions, stub/implementation linking
- **WebSocket / SSE** — Real-time endpoint registration and handler mapping

### Messaging & Event Systems

- **Kafka** — Consumer/producer extraction, topic dependency graphs
- **RabbitMQ / AMQP** — Queue, exchange, and routing key relationships
- **Spring Cloud Stream** — Binding and channel analysis
- **JMS** — Queue/topic message flow extraction

### Integration Frameworks

- **Apache Camel** — Route definitions and component wiring
- **Spring Integration** — Message channels, transformers, gateways
- **Spring Batch** — Job/step/chunk structure extraction

---

### Multi-Language Support — A Major Expansion

Adding languages beyond Java is a **fundamental shift** in project scope. The current parser, models, resolver pipeline, and output formats are all built around Java's AST and Spring's conventions. Supporting a new language means building a new parser front-end, new framework-specific resolvers, and mapping to a shared graph model — while keeping tree-sitter as the common parsing substrate.

Candidate languages, roughly ordered by how much their ecosystems benefit from the same kind of cross-file relationship extraction that motivated the Java work:

- **Python** (Django, Flask, FastAPI) — Decorator-driven routing, dynamic typing makes static relationship extraction valuable
- **TypeScript / JavaScript** (Express, NestJS, Next.js) — DI in NestJS, middleware chains, module re-exports obscure structure
- **Go** (net/http, Gin, gRPC) — Simpler wiring but interface-based DI and codegen (protobuf, Wire) still benefit from extraction
- **Ruby** (Rails) — Convention-over-configuration hides routes, callbacks, and associations from file-level reading
- **Rust** (Actix, Axum) — Trait-based dispatch and macro-heavy routing benefit from static extraction

Each language is a significant standalone effort and an architecture plan on what would be shared between languages would be a first step.
Then build language-specific parser front-ends that emit into that shared architecture.

---

## 2. Deeper Static Analysis

### Transaction Boundary Mapping

- Extract `@Transactional` propagation across call chains
- Map isolation levels and read-only flags per method

### Async & Reactive Flow Extraction

- Track `@Async` method boundaries and executor assignments
- Map `CompletableFuture` chains and compositions
- Extract reactive stream operator chains (WebFlux)

### Data Transformation Tracking

- Follow DTO-to-entity and entity-to-DTO conversions through layers
- Map field-level data flow across method boundaries

### Multi-Repository Analysis

- Service dependency mapping across repositories (API client ↔ controller matching)
- Shared library impact analysis (which services consume which library classes)
- API contract extraction for cross-repo compatibility checking

---

## 3. Code Graph & Queryability

### Enrich the Graph Model

Extend the current Pydantic model into a richer, queryable graph:

- **Nodes:** classes, methods, endpoints, fields, annotations, configuration properties, message topics
- **Edges:** calls, injects, implements, extends, produces-to-topic, consumes-from-topic, maps-to-endpoint
- **Properties:** FQN, file path, line range, annotation metadata, HTTP method/path, visibility

### Query Interface

Expose the graph through a structured query layer that supports:

- **Traversal queries** — "What services does this controller depend on, transitively?"
- **Impact queries** — "Which endpoints are affected if I change this repository method?"
- **Subgraph extraction** — "Give me the full dependency subgraph rooted at `OrderService`."
- **Filter + projection** — Select nodes by annotation, package, type, or relationship depth

Query results should be exportable as JSON, GraphML, or Markdown.

### Source Attribution & Citation

Every node and edge in the graph **must** carry provenance metadata:

- **File path** and **line range** (start line, end line) for every extracted element
- **Commit SHA** (optional, when available) tying the extraction to a specific repo state
- **Extraction method** — which parser pass or resolver produced the relationship

When the graph is used to generate artifacts:

- Each fact in the output includes a **citation** back to its source location (`file:line`)
- Aggregated outputs (e.g., Markdown reports) include a **References** section listing all source files and line ranges consulted
- Citations remain stable across re-analysis of the same commit (deterministic extraction)

This makes every claim in a generated artifact **verifiable** — a reader can trace any statement back to the exact source code that produced it.

---

## 4. Visualization

- **Dependency graphs** — Component and service relationship diagrams
- **Sequence diagrams** — Auto-generated from extracted call chains
- **Architecture layer diagrams** — Package/module boundary visualization
- **Data flow diagrams** — How data moves through controller → service → repository

---

## 5. Historical & Evolution Analysis

- **Architecture evolution** — Track structural changes across commits/tags
- **Incremental analysis** — Re-analyze only changed files, merge with cached results
- **Refactoring impact estimation** — Use the dependency graph to scope blast radius of a proposed change

---

## 6. Performance & Scale

- **Incremental parsing** — Skip unchanged files using content hashing
- **Parallel file processing** — Distribute tree-sitter parsing across threads/processes
- **Streaming analysis** — Process files as a stream rather than loading all into memory
- **Graph backend options** — Optional Neo4j or SQLite backends for large codebases where in-memory graphs don't fit

---

## 7. LLM Context & Developer Experience

- **Auto-generated project summaries** — Structure and key component overviews from the graph
- **Interactive code tours** — Guided walkthroughs generated from call-chain analysis
- **Test impact analysis** — Use the dependency graph to determine which tests cover changed code
- **Dependency explanations** — "Why does X depend on Y?" answered via shortest path in the graph
