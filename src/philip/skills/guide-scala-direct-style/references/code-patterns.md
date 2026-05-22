# Direct-Style Scala 3 Code Patterns

Quick-reference snippets for the most common patterns in direct-style Scala 3
applications. Each pattern shows the idiomatic approach and explains why it's
preferred over alternatives.

---

## Tapir Endpoint (direct-style)

Use `.handle...` methods — they work synchronously without a monadic wrapper.
The older `.serverLogic` family returns `F[Either[E, O]]` which is unnecessary
in direct style.

```scala
val statusEndpoint = endpoint.get
  .in("status")
  .out(stringBody)
  .handleSuccess(_ => "OK")
```

## OxApp Entry Point

`OxApp` provides an `Ox` scope for the entire application lifetime. Resources
registered with `useInScope` / `useCloseableInScope` are released in reverse
order on shutdown.

```scala
object Main extends OxApp:
  override def run(args: Vector[String])(using Ox): ExitCode =
    val server = useCloseableInScope(startServer())
    never // block until shutdown signal
```

## Structured Concurrency

Prefer creating nested, local scopes over propagating `using Ox` through your
call chain. Broad propagation defeats the safety guarantees of structured
concurrency — a leaked `Ox` reference lets code fork threads outside the
intended lifecycle.

```scala
def processItems(items: List[Item]): List[Result] =
  supervised:
    val results = items.map: item =>
      fork(process(item))
    results.map(_.join())
```

## Immutable State Pattern

The goal is to keep mutation contained to a single, visible point. Business
logic operates on immutable `State` objects via pure functions. Only the
top-level loop holds a `var` — this makes concurrent access impossible to
misuse, because the mutable reference never escapes.

```scala
case class ViewState(
  buckets: Map[HourKey, BucketState],
  offsets: Map[Partition, Offset]
)

// Pure function: old state in, new state out
def processBatch(state: ViewState, events: List[Event]): ViewState =
  events.foldLeft(state): (s, event) =>
    s.copy(buckets = s.buckets.updated(event.hourKey, ...))

// Single mutable point at the top level
var current = ViewState.empty
for batch <- consumer.poll() do
  current = processBatch(current, batch)
```

## Channel Communication

Ox `Channel`s replace shared mutable state for inter-thread communication.
They're typed, bounded, and integrate with structured concurrency — when the
scope ends, channels are closed and threads are interrupted.

```scala
supervised:
  val channel = Channel.buffered[Event](128)
  forkUser:
    for event <- source do
      channel.send(event)
  forkUser:
    forever:
      val event = channel.receive()
      process(event)
```

## Testing HTTP Endpoints

Use `TapirSyncStubInterpreter` for in-process endpoint tests — no real HTTP
server needed. Combine with `SttpClientInterpreter` for type-safe request
building.

```scala
val backend = TapirSyncStubInterpreter()
  .whenServerEndpointRunLogic(serverEndpoint)
  .backend()

val response = basicRequest
  .get(uri"http://test/status")
  .send(backend)

assertEquals(response.body, Right("OK"))
```

## Error Handling with Ox `either`

Ox's `either` block with `.ok()` provides short-circuit error handling without
monadic types. Errors are returned as `Left`, success as `Right`.

```scala
def findUser(id: UserId): Either[Fail, User] = either:
  val record = db.find(id).ok()           // short-circuits on None/Left
  val profile = fetchProfile(record).ok()  // chains cleanly
  User(record, profile)
```

## Resource Management

Track ownership explicitly. The component that creates a resource owns its
lifecycle. Use `useInScope` to bind resource cleanup to a structured scope.

```scala
supervised:
  val pool = useCloseableInScope(HikariPool(config))
  val producer = useCloseableInScope(KafkaProducer(kafkaConfig))
  val server = useCloseableInScope(startServer(pool, producer))
  never
  // on shutdown: server closed, then producer, then pool (reverse order)
```
