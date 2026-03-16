# Why Repo Atlas Exists

## Code Understanding Is Not a Context Window Problem

The question people ask is: "Why do you need a separate tool when models can ingest a million tokens and agentic harnesses can explore iteratively?" Fair question. Here's the answer.

In Spring applications, the hardest questions require deterministic multi-stage resolution. To trace which frontend call maps to which BFF endpoint, which BFF endpoint reaches which backend controller, which service and repository paths get exercised, and which properties, constants, and injected dependencies affect behavior along the way, you have to resolve multiple layers of indirection across files and packages:

- Spring dependency injection wiring
- Annotations and route mappings
- Constants and configuration properties with profile overrides
- Type references across package boundaries
- Service-to-service handoffs

Give a frontier model the full codebase in a million-token window and ask it to trace one of these paths. It will fail in some meaningful way every time. Not because the model is stupid. Because thinking tokens are not a substitute for exhaustive, nested resolution across layers of indirection. The model can reason about what it sees, but it cannot systematically *trace* through these chains the way a parser can. More context and more thinking tokens do not produce a complete architectural trace. They produce a plausible-sounding partial one.

## Agentic Harnesses Improve the Odds But Still Don't Scale

Claude Code, Codex, and similar tools do better because they iterate. They search, take notes, revisit assumptions, build up understanding over multiple turns. For a focused question in a single service, an agent has a real shot at getting there.

But every question starts from zero. The agent walks the chain again — grepping, reading files, following imports, inferring wiring — burning tokens on the same discovery work it did last time. Even with grep or RAG, the best case is a probabilistic walk through embeddings that *might* land on the right files in the right order. It's slow, expensive, and non-deterministic. Two runs on the same question can produce different answers, and you have no way to verify what was missed.

Repo Atlas eliminates this entirely. It computes the structural map once and writes it to a persistent artifact. That artifact is the answer. Every agent, every question, every run reads the same resolved map — instantly, deterministically, correctly. No chain-walking. No token burn. No hoping RAG found the right context. The artifact is a massive speed-up precisely because it converts an O(n)-token discovery problem into an O(1) file read.

The difference is not incremental. An agent using RAG to trace a dependency injection chain across three services might spend dozens of tool calls, thousands of tokens, and still arrive at a partial or wrong answer. An agent reading the Repo Atlas artifact gets the complete, correct answer in one read. Same question, same codebase — one approach is fast, deterministic, and reliable; the other is slow, probabilistic, and fragile.

This distinction matters most at scale. When the task moves beyond one service to cross-service analysis, the agent-only approach breaks down:

- It's slower by orders of magnitude
- It burns far more tokens reconstructing what a persistent artifact already contains
- It repeats the same discovery work on every run
- It remains non-deterministic — different runs produce different coverage
- Coverage is uneven and you can't verify what it missed

That last point is the dangerous one. When you're assessing blast radius for a change, finding all consumers of a contract, or checking for regressions during an upgrade, missing one linkage is enough to produce a false sense of safety. If the agent never inspects a downstream service it should have checked, that gap stays invisible until something breaks in production. A persistent artifact doesn't have gaps — it resolved every file in the codebase the same way, every time.

## Persistent Artifacts Change the Economics

The core insight is that structural resolution is separable from reasoning. The resolution work — tracing injection chains, expanding constants, resolving routes across packages — is deterministic and cacheable. The reasoning work — answering questions about behavior, assessing impact, planning changes — is what LLMs are built for.

Without Repo Atlas, agents conflate the two. They spend most of their token budget on resolution (the part they're bad at) and have less left for reasoning (the part they're good at). Persistent artifacts flip this: resolution happens once, offline, and every subsequent agent interaction starts with the answer already materialized. The speed-up compounds with team size and question volume — the artifact is computed once but read by every agent, every developer, every CI check that needs architectural context.

## What Repo Atlas Actually Produces

Repo Atlas runs tree-sitter-based static analysis against Java Spring applications and builds a resolved structural map. Concretely, it extracts and connects:

- REST endpoints and route mappings
- Controller, service, and repository relationships
- Dependency injection chains
- Constant and property resolution (including profile overrides)
- Type usage across packages
- A navigable graph of architectural connections within and across services

This changes the problem from "Can the model discover architecture from raw source?" to "Can the model reason over an accurate architectural representation?" That second question is what LLMs are actually good at.

Repo Atlas does the structural resolution work that models fail at reliably, so they can spend their effort on reasoning instead of reconstruction.

## OpenAPI for Codebases That Never Set It Up

One practical consequence: the Repo Atlas artifact is effectively an OpenAPI/Swagger-style endpoint catalog — extracted from source code, not from runtime scaffolding. Many Spring codebases were never set up with Springdoc, Springfox, or any OpenAPI generator. There's no `/v3/api-docs` endpoint, no generated spec, no contract file checked into the repo. The endpoint surface is defined implicitly across scattered controller classes, annotation hierarchies, constant-based path segments, and profile-dependent property values.

For these codebases, discovering the full API surface today means either reading every controller by hand or hoping an agent can grep its way to a complete picture. Repo Atlas produces the resolved catalog directly from the source — every endpoint, every HTTP method, every resolved path including constants and property placeholders — without requiring the application to compile, run, or have any OpenAPI tooling configured.

This matters beyond documentation. Teams that lack a formal API spec often lack the downstream benefits that flow from it: contract testing, client generation, automated compatibility checks, migration planning. The Repo Atlas artifact can serve as the input to those workflows even when the codebase itself was never wired for them.

## Why Vector Search Alone Isn't Enough

The same principle applies to code search. Pure vector search and vanilla RAG work for simple demos. Real codebases are harder because the important relationships are often structural, not lexical. The relevant code may be connected through injection chains or service calls, not through textual similarity. A developer searching often remembers approximate behavior rather than exact symbol names. Multiple partial candidates may need to be found and re-ranked together.

Production-grade code search needs hybrid retrieval, and the top AI-enabled IDEs already do this. Cursor and others don't rely on vector search alone. They combine semantic search (for fuzzy recall and behavioral descriptions), lexical and structural search (for symbol lookup, AST-level queries, and exact identifiers), and graph search (for traversing relationships like controller to service to repository, or endpoint to downstream dependency).

Repo Atlas improves all three modes because it pre-processes the code into clean, resolved, structured data. That gives the search system something far more useful to index than raw source text. The graph and semantic layers work better when they're built on top of deterministic resolution rather than token soup.
