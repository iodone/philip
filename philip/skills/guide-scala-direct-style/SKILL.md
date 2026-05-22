---
name: guide-scala-direct-style
version: 1.0.0
description: >
  Guide for generating direct-style Scala 3 applications using Tapir, Ox, sttp,
  and virtual threads on JVM 21+. Use this skill whenever building, scaffolding,
  or generating a Scala 3 backend service — especially when using direct style
  (no Future, no IO, no cats-effect). Also use when writing AGENTS.md rules for
  Scala projects, composing prompts for autonomous Scala code generation, or
  setting up sbt projects with Tapir/Ox. Trigger on mentions of: Scala 3,
  direct style, Tapir, Ox, sttp, OxApp, structured concurrency in Scala,
  braceless Scala syntax, or Metals MCP for Scala.
---

# Scala 3 Direct-Style Development

**HARD GATE:** This skill only does three things: set up project AGENTS.md,
compose generation prompts, and route to direct-style guide chapters.
Do not generate cats-effect/ZIO code. Do not use `.serverLogic` — only `.handle...`.
Do not write imperative Scala with mutable collections or shared mutable state.

Generate well-structured direct-style Scala 3 applications — the kind that use
virtual threads, structured concurrency, and synchronous APIs instead of
monadic effect systems like cats-effect or ZIO.

Based on real-world experience from [SoftwareMill's blog post](https://blog.softwaremill.com/generating-direct-style-scala-3-apps)
and the [Bootzooka](https://github.com/softwaremill/bootzooka) template.

---

## Tech Stack

| Layer | Choice | Notes |
| :--- | :--- | :--- |
| Language | Scala 3.x | Braceless syntax, enums, opaque types, givens |
| Runtime | JVM 21+ | Virtual threads via `PropagatingVirtualThreadFactory` |
| HTTP | [Tapir](https://tapir.softwaremill.com/) | `.handle...` API (not `.serverLogic`) |
| Concurrency | [Ox](https://ox.softwaremill.com/latest/) | `OxApp`, `supervised`, `fork`, `Channel` |
| HTTP Client | [sttp](https://sttp.softwaremill.com/) | Type-safe client with Tapir integration |
| Build | sbt | Use `sbt --client` for speed |
| Tests | munit | With `TapirSyncStubInterpreter` |

---

## Phase 1: Set Up Project AGENTS.md

**Entry:** New Scala 3 direct-style project, or existing project without AGENTS.md.

Read `references/agents-md-template.md` for the full template. Copy it into the
project's `AGENTS.md` and adjust as needed.

The template covers: sbt workflows, Metals MCP tool usage, direct-style Tapir
APIs, Ox concurrency rules, functional programming style, and coding conventions.

**Exit conditions:**
- AGENTS.md exists and contains direct-style rules → proceed to Phase 2
- Project already has AGENTS.md with direct-style rules → skip to Phase 2

**Escape hatch:** If user says "I already have AGENTS.md" or provides their own
rules → skip to Phase 2 directly.

**STOP.** Confirm AGENTS.md is in place before composing the prompt.

---

## Phase 2: Compose the Generation Prompt

**Entry:** AGENTS.md is configured. User wants to generate an application.

A complete prompt has four parts:

```
┌──────────────────────────────────────────────┐
│ 1. Problem statement (1-2 sentences)         │
│ 2. Development process (plan → implement)    │
│ 3. Tech stack + direct-style guide reference │
│ 4. Feature specifications                    │
└──────────────────────────────────────────────┘
```

### Part 1 — Problem statement

Keep it brief. Add a "no over-engineering" guardrail:

```
Build a service that [does X, Y, Z].

Do not invent new features, or over-complicate. Keep it simple, implementing
only what's required, as described by the specification.
```

### Part 2 — Development process

Include plan-then-implement instructions with code review loops:

```
# Development process

## Write a plan
First write a step-by-step implementation plan. Store the plan in `plan.md`.
Do not include any code in the plan.
* Tasks designed to be implemented individually, one by one
* Grouped by feature / technical concern
* Each task handles a single concern
* No additional features beyond requirements

## Implement
Execute the plan step by step:
* Code MUST compile without warnings, tests MUST pass
* Unit tests: focused, non-overlapping, one scenario each
* After completing all tasks from a task group, ALWAYS perform a code review
  taking into account the coding guidelines. You MUST run a code review before
  proceeding to the next task group.
* ALWAYS apply code review remarks, then repeat review. No remarks → next group.
* All features integrated — no dead or unreachable code
* Commit after each task, mark as done in plan.md

Work autonomously. Do not ask questions, resolve issues on your own.
```

The code review loop is the single most effective quality lever for autonomous
generation. Review by task *group* (not per-task) because LLMs tend to "forget"
review instructions after 1-2 tasks.

### Part 3 — Tech stack + guide reference

```
# Tech stack
* scala 3.8.x on JVM 21
* sbt build system
* direct-style approach (no Future, no IO, no cats-effect)
* functional programming (immutable data types, pure functions)
* scala 3 features (enums, opaque types, inlines, extension methods, givens)
* tapir for HTTP
* ox for direct-style structured concurrency and streaming
* munit for tests

When implementing direct-style applications using Tapir, Ox, or sttp,
consult the guide at:
https://github.com/VirtusLab/direct-style-guide/blob/master/index.md

Fetch the chapter relevant to your current task for implementation patterns.
Base URL for chapters:
https://github.com/VirtusLab/direct-style-guide/blob/master/
```

Add project-specific libraries (scalaxb, circe, etc.) as needed.

### Part 4 — Feature specifications

Read `references/example-spec.md` for a complete 10-feature example showing how
to write specs. Key principles:

- Number features incrementally; start with a skeleton (health-check endpoint)
- Describe behavior, not implementation — give the AI room to choose approaches
- For external systems (Kafka, S3, DB): require an abstract interface + test impl
- List specific test scenarios when behavior is non-trivial
- Call out constraints explicitly ("not in memory", "no auto-commit")
- State inter-feature dependencies ("inject into the service")

```
GOOD: "Abstracts storage behind an interface (S3 impl + in-memory test impl)"
BAD:  "Use AWS S3 SDK to upload files" (prescribes implementation, no test path)

GOOD: "Storing event lists in memory is not an option — too many events"
BAD:  "Process events efficiently" (vague, agent will pick the obvious-but-wrong approach)

GOOD: "The service accepts an event producer interface (no-op for now — Kafka comes later)"
BAD:  "Add Kafka" in Feature 2 when Kafka is Feature 6 (coupling, no incremental build)
```

**Exit conditions:**
- Prompt assembled with all 4 parts → proceed to Phase 3
- User only needs AGENTS.md, no prompt → complete as DONE

**Escape hatch:** If user provides a complete prompt already → skip to Phase 3.

**STOP.** Share the composed prompt with the user for review before generation.

---

## Phase 3: Route to Direct-Style Guide Chapters

**Entry:** Prompt is ready, or user is mid-implementation and needs specific patterns.

The [direct-style-guide](https://github.com/VirtusLab/direct-style-guide) is an
AI-generated-for-AI reference extracted from the Bootzooka template. Point the
LLM at the index and let it fetch chapters on demand.

**Index**: https://github.com/VirtusLab/direct-style-guide/blob/master/index.md

| # | Chapter | When to fetch |
| :--- | :--- | :--- |
| 01 | Resource Management | Setting up `useInScope`, cleanup ordering |
| 02 | Background Processes | `OxApp`, `fork`/`forkUser`, periodic loops |
| 03 | Type-Safe Configuration | PureConfig, env var overrides, `Sensitive` |
| 04 | Compile-Time DI | MacWire `autowire`, endpoint collection |
| 05 | Error Handling | `Fail` ADT, Ox `either` + `.ok()` short-circuit |
| 06 | Error Output Customisation | Custom error responses, `failOutput` |
| 07 | Decode Failure Handling | `DefaultDecodeFailureHandler` customization |
| 08 | Authentication | `secureEndpoint`, `Auth[T]`, `handleSecurity` |
| 09 | HTTP Server Configuration | Headers, CORS, SPA files, `NettySyncServer` |
| 10 | SQL Persistence | Magnum, `@Table`, `DbCodec`, Flyway |
| 11 | Version API | `sbt-buildinfo` + git hash |
| 12 | Sending Emails | Pluggable senders, background batch |
| 13 | Compile-Time OpenAPI | Build-time YAML generation |
| 14 | Testing HTTP Endpoints | `TapirSyncStubInterpreter`, stub backends |
| 15 | OpenTelemetry Observability | Tracing, metrics, `PropagatingVirtualThreadFactory` |
| 16 | Kafka Streaming | `KafkaFlow`, `KafkaDrain`, offset commits |

For code pattern examples (endpoints, OxApp, concurrency, state, testing), read
`references/code-patterns.md`.

---

## Common Pitfalls

These are the most frequent mistakes when generating direct-style Scala 3 code:

| What goes wrong | Why | How to prevent |
| :--- | :--- | :--- |
| LLM defaults to cats-effect | Dominant in training data | State "direct-style, no Future, no IO" explicitly |
| Uses `.serverLogic` | Older Tapir API is more common | AGENTS.md enforces `.handle...` |
| Excessive mutable state | Imperative habits | Require immutable State + pure functions |
| Propagates `using Ox` everywhere | Misunderstands structured concurrency | Emphasize nested local scopes |
| Slow sbt invocations | Cold start every time | Enforce `sbt --client` |
| Ignores Metals MCP tools | Prefers bash | AGENTS.md: "ALWAYS use tools" |
| Skips code reviews | Forgets after task 1-2 | Review by task *group*, not per-task |
| Virtual thread context lost | OTel propagation not configured | Fetch guide chapter 15 |

```
GOOD: val statusEndpoint = endpoint.get.in("status").out(stringBody).handleSuccess(_ => "OK")
BAD:  val statusEndpoint = endpoint.get.in("status").out(stringBody).serverLogic(_ => Right("OK"))
      (serverLogic requires monadic wrapping — handle is the direct-style API)

GOOD: supervised:
        val results = items.map(item => fork(process(item)))
        results.map(_.join())
BAD:  def processItems(items: List[Item])(using Ox): List[Result] = ...
      (propagating Ox through the call chain leaks the scope boundary)

GOOD: case class State(buckets: Map[Key, Bucket])
      def process(s: State, e: Event): State = s.copy(...)
      var current = State.empty  // local var only
BAD:  class Builder { val buckets = mutable.Map[Key, Bucket]() }
      (shared mutable state — concurrent access bugs, hard to test)
```

---

## Self-Regulation

- If `sbt compile` fails 3 consecutive times on the same error → **STOP**, report
  the error and what was attempted
- If the code review loop produces remarks 3 times on the same issue → **STOP**,
  the approach likely needs rethinking
- If a guide chapter fetch returns 404 or empty content → skip it, note the gap,
  continue with available knowledge
- If the generated prompt exceeds 5000 words → warn that it may exceed context
  limits for some models

---

## Bundled References

| File | Contents | When to read |
| :--- | :--- | :--- |
| `references/agents-md-template.md` | Complete AGENTS.md for Scala projects | Phase 1: setting up a new project |
| `references/code-patterns.md` | Idiomatic code snippets with explanations | Phase 3: writing or reviewing Scala code |
| `references/example-spec.md` | Full 10-feature spec (SOAP/Kafka/S3) | Phase 2 Part 4: writing feature specifications |

---

## External Resources

| Resource | URL |
| :--- | :--- |
| Direct Style Guide | https://github.com/VirtusLab/direct-style-guide |
| Bootzooka template | https://github.com/softwaremill/bootzooka |
| Example project | https://github.com/VirtusLab/scala-kafka-soap |
| AGENTS.md gist | https://gist.github.com/adamw/4874bd32dda523b75fedba62cbcce0c7 |
| Prompt template gist | https://gist.github.com/adamw/a2d3cea5d7bd54006b6541c813dcf416 |
| Tapir docs | https://tapir.softwaremill.com/ |
| Ox docs | https://ox.softwaremill.com/latest/ |
| Metals MCP guide | https://softwaremill.com/a-beginners-guide-to-using-scala-metals-with-its-model-context-protocol-server/ |

---

## Completion States

- **DONE** — AGENTS.md configured + prompt composed + guide chapters routed
- **DONE_WITH_CONCERNS** — completed but some guide chapters returned 404 or
  a pitfall was encountered that couldn't be fully resolved; concerns listed
- **BLOCKED** — cannot proceed (e.g., sbt won't compile, guide index unreachable);
  report: STATUS + REASON + ATTEMPTED + RECOMMENDATION
- **NEEDS_CONTEXT** — missing information to proceed (e.g., unclear tech stack
  requirements, no feature spec provided); list what's needed
