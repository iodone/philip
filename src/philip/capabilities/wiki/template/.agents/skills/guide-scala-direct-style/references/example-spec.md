# Example Feature Specification: SOAP/Kafka/S3 Train Event Service

This is a complete, real-world example of a feature specification used to
autonomously generate a direct-style Scala 3 application. Study it for
spec-writing style and granularity — then write your own specs following the
same patterns.

Source project: https://github.com/VirtusLab/scala-kafka-soap

---

## Problem Statement

```
Build a service that receives SOAP notifications about train arrivals and
departures, publishes them to Kafka, and materializes hourly event views in S3.
```

---

## Features

### 1. Project Setup — Status Endpoint

Set up a greenfield project with a `GET /status` health-check endpoint returning
`"OK"`. The HTTP server runs on port 8080.

### 2. SOAP Train Information Service

Add a SOAP 1.1 web service at `/soap/TrainInfoService` with three operations
routed by the `SOAPAction` header:

- **NotifyArrival**: accepts arrival details, returns confirmationId and
  receivedAt.
- **NotifyDeparture**: accepts departure details, returns confirmationId and
  receivedAt.
- **GetTrainStatus**: accepts trainNumber, returns current status. Returns a
  SOAP fault if train not found.

The XSD schema is provided in `train-info.xsd`. Generate typed classes from it.
Build codecs that decode/encode SOAP envelopes. A catch-all endpoint returns a
SOAP fault for unknown actions.

The service accepts an event producer interface (no-op for now — Kafka comes
later). Unit tests use HTTP stub/mock servers.

### 3. OpenTelemetry Tracing and Metrics

Add OpenTelemetry with auto-configuration. Instrument HTTP endpoints with
tracing and metrics. Thread the OpenTelemetry instance to components that need
it. Ensure runtime metrics resources are closed on shutdown.

### 4. Logging

Add structured logging. Provide a reusable logging facility for service classes.
Use parameterized log messages (not string interpolation).

### 5. SOAP Error Handling

Add custom error handlers that return proper SOAP faults for requests on SOAP
paths:

- Decode/parse failures → SOAP Client Fault
- Rejected requests → SOAP Client Fault
- Unhandled exceptions → SOAP Server Fault

Non-SOAP paths use the framework's default error handling.

### 6. Kafka Event Publishing

Add Kafka integration:

- An event producer interface with `publishArrival` and `publishDeparture`,
  supporting resource cleanup
- A `TrainEvent` model with event type, train details, timestamp, and optional
  arrival/departure fields, serialized as JSON
- A Kafka implementation publishing to topic `train.events` with trainNumber as
  key
- Inject into the service — publish after successful notify operations

Unit tests should use a no-op Kafka producer.

### 7. S3 Event View Builder

Add an Event View Builder that consumes from Kafka and materializes hourly JSONL
files to S3:

- Consumes from `train.events` (consumer group `event-view-builder`, no
  auto-commit)
- Buckets events by UTC hour into local staging files, each line a JSON record
  containing the Kafka offset and event data
- Periodically flushes dirty buckets to S3 (default every 10 minutes)
- **Dedup**: per-bucket, per-partition offset tracking — skips events already
  stored. On startup, efficiently rebuilds offset state from existing files
  (downloaded from S3 if needed)
- Storing event lists in memory is not an option — there might be too many
  events, which might cause running out of memory
- **Late events**: drops events older than 3 hours
- **Safe flush**: only commits Kafka offsets when ALL dirty buckets uploaded
  successfully — partial failures retry on next flush without committing,
  preventing data loss
- **Lifecycle**: closes file handles on shutdown, cleans up temp directory
- Abstracts storage behind an interface (S3 implementation + in-memory test
  implementation)
- Purges local files for sealed buckets (older than 3 hours) after each flush

Tests cover: first startup, crash recovery from S3, late event dropping,
independent bucket de-dup, upload failure retry.

### 8. Event View Builder Metrics

Add OpenTelemetry metrics to the Event View Builder and integrate them. Provide
a noop default for tests.

- Count events processed by reason (appended / dropped / skipped duplicate)
- Count flush outcomes (success / failure)
- Histogram for flush duration
- Gauge for number of dirty buckets

### 9. Typed Configuration

Replace environment variables and hardcoded values with a typed configuration
file:

- Define a config model covering: Kafka bootstrap servers, S3 bucket name, HTTP
  port, flush interval
- Load from a config file with sensible defaults for local development
- Support environment variable overrides
- Fail fast on invalid config at startup

### 10. OpenAPI Documentation

Expose auto-generated OpenAPI documentation via Swagger UI at `/docs`, covering
all HTTP endpoints.

---

## Spec-Writing Patterns to Notice

| Pattern | Where It Appears | Why It Matters |
| :--- | :--- | :--- |
| Incremental scaffolding | Feature 1 sets up the skeleton first | Gives early compilation feedback; each later feature builds on a working base |
| Interface-first design | Feature 2: "accepts an event producer interface (no-op for now)" | Decouples concerns; enables testing without real infrastructure |
| External system abstraction | Feature 7: "abstracts storage behind an interface" | S3 impl + in-memory test impl — same code path, different backends |
| Explicit test scenarios | Feature 7 lists 5 specific test cases | Removes ambiguity about "what counts as tested" |
| Cross-cutting concerns separated | Features 3, 4, 8 are standalone observability features | Avoids mixing infra plumbing into business logic features |
| Constraints stated explicitly | Feature 7: "storing event lists in memory is not an option" | Prevents the obvious-but-wrong approach; forces stream-based design |
| Inter-feature dependencies called out | Feature 6: "inject into the service — publish after successful notify" | Makes integration order clear without prescribing implementation |
