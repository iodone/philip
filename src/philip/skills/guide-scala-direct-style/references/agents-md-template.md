# AGENTS.md Template for Direct-Style Scala 3 Projects

Copy this into the project's `AGENTS.md` file. It steers AI assistants toward
correct direct-style Scala 3 code — the right sbt workflows, Tapir APIs,
Ox concurrency patterns, and functional style.

Adjust per-project (e.g., add library-specific rules, remove irrelevant sections).

---

```markdown
You are an expert backend software engineer and architect.

# Scala projects

* ALWAYS use tools to compile and run tests instead of relying on bash commands
* after adding a dependency to `build.sbt`, ALWAYS run the `import-build` tool
* to lookup a dependency or the latest version, use the `find-dep` tool
* to lookup the API of a class, use the `inspect` tool
* use `sbt --client` instead of `sbt` to connect to a running sbt server for
  faster execution
* to verify that the app starts use `sbt run`, WITHOUT `--client`, as it
  prevents interrupting the process
* before committing, ALWAYS format all changed Scala files using the sbt
  `scalafmt` plugin: `sbt --client scalafmtAll`
* avoid using `{}` and use braceless syntax
* NEVER use non-local returns
* ALWAYS use functional programming: immutable data types, pattern matching,
  immutable collections, higher order functions, algebraic data types
* instead of mutable state, ALWAYS prefer writing testable, pure functions that
  accept and return a state data type. Use mutable state only locally at the
  top-level

# Direct-style Scala

* in Tapir, use the `.handle...` methods instead of `.serverLogic...` ones
* in Tapir, when testing, avoid using `IdentityMonad`, instead use dedicated
  synchronous utilities, e.g. `BackendStub.synchronous`
* using `OxApp` to implement proper resource management on shutdown
* only propagate concurrency scope (`using Ox`) when absolutely needed. Prefer
  creating nested, local, structured concurrency scopes instead.
* use Ox's `Channel`s to communicate between threads instead and to avoid shared
  mutable state

# Coding style

* take care of good naming; responsibilities in code should be segregated
  between appropriately named entities
* when dealing with resources, properly track who owns which resources, and
  ensure proper ordering on cleanup
* when possible, restrict visibility of classes and top-level constructs to
  appropriate sub-packages. No need to restrict visibility to the main package.
* it's fine to create multiple classes in one file, especially if they are used
  only by that class
* AVOID using global mutable state. Instead use immutable state that is passed &
  returned from functions. Local mutable state, such a mutable variables tightly
  scoped in a method are fine
* AVOID shared mutable state at any cost
* AVOID using mutable collections
* comment on any aspects that aren't obvious from the implementation, but are
  important to know when reading the code

# Git

* always create new commits, instead of amending existing ones
```

---

## Why each rule matters

| Rule | Rationale |
| :--- | :--- |
| `sbt --client` | Cold sbt startup is ~5-10s; client mode reuses a warm server |
| `sbt run` without `--client` | Client mode forks to background — no way to Ctrl-C a runaway app |
| Metals MCP tools | 10x faster than shelling out to `sbt`; provides symbol inspection, dep lookup |
| `.handle...` over `.serverLogic` | Direct-style Tapir API — no monadic wrapper needed |
| `BackendStub.synchronous` | The direct-style test stub; `IdentityMonad` is from the legacy API |
| Local `using Ox` scopes | Propagating `Ox` broadly defeats structured concurrency's safety guarantees |
| Immutable state + local var | Keeps mutation contained; pure functions are easier to test and reason about |
| Braceless syntax | Scala 3 idiomatic style — reduces visual noise |
