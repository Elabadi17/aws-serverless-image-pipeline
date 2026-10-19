# Architecture decision records

Short records of the choices that shape this project, with the alternatives considered.

---

## ADR-01 — Presigned S3 POST instead of uploading through API Gateway

**Context.** Images can be up to 20 MB. API Gateway has a 10 MB payload limit and Lambda a 6 MB synchronous payload limit.

**Decision.** `POST /uploads` returns a presigned **POST** (not PUT). The client sends the file straight to S3.

**Why POST rather than PUT.** A presigned POST carries a *policy* that S3 enforces: exact key, `Content-Type`, and `content-length-range`. A presigned PUT cannot limit the size.

**Consequences.** No compute is billed during the transfer; uploads scale with S3, not Lambda. The client needs two calls (get URL, then upload).

---

## ADR-02 — S3 → SQS → Lambda dispatcher → Step Functions

**Context.** S3 can notify Lambda, SQS, SNS or EventBridge. Step Functions can't be an S3 notification target directly.

**Options considered.**

| Option | Verdict |
|---|---|
| S3 → Lambda that does all the work | No buffering, retries limited to async-invoke defaults, one big function |
| S3 → EventBridge rule → Step Functions | Fewer moving parts, but no queue to absorb bursts or to inspect failed events, and the brief asks for SQS + DLQ |
| **S3 → SQS → dispatcher → Step Functions** | Buffering, back-pressure (capped concurrency), DLQ, clear separation between *intake* and *processing* |

**Decision.** SQS in front, a tiny dispatcher Lambda that starts one execution per image.

**Consequences.** One extra (cheap) Lambda. In exchange, a downstream outage never loses events: they wait in the queue, then in the DLQ.

---

## ADR-03 — Execution name = imageId for idempotency

S3 event notifications are *at least once*. The dispatcher starts the execution with `name = imageId`. Step Functions Standard rejects a second execution with the same name for 90 days (`ExecutionAlreadyExists`), which the dispatcher treats as success. No extra deduplication table needed.

---

## ADR-04 — Standard workflow, not Express

Express is cheaper for very high volumes, but is *at least once*, has no name-based idempotency, and keeps history only in CloudWatch Logs. For an image pipeline where each execution is worth inspecting and must run exactly once, Standard fits better. Reconsider if volume reaches millions of images per day.

---

## ADR-05 — Three task Lambdas sharing one package

`validate`, `thumbnail` and `watermark` are separate functions (separate memory sizes, IAM permissions and metrics) but ship from **one code package** plus **one Pillow layer**. One build artefact, no duplicated code, still least privilege at runtime.

---

## ADR-06 — DynamoDB and SNS called directly by Step Functions

Status updates and notifications use the optimised `dynamodb:updateItem` and `sns:publish` integrations. Writing Lambdas for these would add code, cold starts and cost for no benefit.

---

## ADR-07 — HTTP API instead of REST API

The API is a thin Lambda proxy. HTTP API is cheaper, has lower latency and native CORS. REST API would be needed for usage plans/API keys, request validation models or direct WAF association — none of which this project uses yet (WAF is on the roadmap via CloudFront).

---

## ADR-08 — REJECTED vs FAILED

A corrupt upload is expected behaviour, not an incident. `InvalidImageError` is caught separately: status `REJECTED`, the execution **succeeds**, no alarm. Everything else ends in `FAILED`, a **failed** execution and an alarm. This keeps the `ExecutionsFailed` alarm meaningful.

---

## ADR-09 — arm64 (Graviton) Lambdas and a pip-built layer

Graviton is cheaper per GB-second and Pillow publishes `manylinux` wheels for `aarch64`, so the layer is built with `pip --platform ... --only-binary=:all:` — no Docker needed. The architecture is one Terraform variable; `make deploy ARCH=x86_64` switches both function and layer.

---

## ADR-10 — Breaking the Terraform dependency cycle

The state machine references the task Lambdas, and the dispatcher Lambda needs the state machine ARN. Because all functions come from a single `for_each` resource, a direct reference would create a cycle. The ARN is therefore **built from the state machine name** in `main.tf` (`local.state_machine_arn`), and the SQS event source mapping `depends_on` the state machine so no event is consumed before the workflow exists.
