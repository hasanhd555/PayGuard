# Example AWS architecture: asynchronous complaint triage

This maps the [production memo](Production_Design_Memo.md) to concrete services
using the proposed S3, event, queue, Lambda, DynamoDB and SNS flow. The model
endpoint, support case system and answering service remain generic so they can
use approved in-country infrastructure. This is an illustrative deployment
architecture, not deployed infrastructure.

## Complaint processing and routing

```mermaid
flowchart LR
    subgraph AWS["AWS services: approved in-country region"]
        S3["Amazon S3<br/>Incoming complaints"] -->|Object-created event| EB["Amazon EventBridge"]
        EB --> Q["Amazon SQS<br/>Processing queue"]
        Q --> W["AWS Lambda<br/>Mask PII, screen, triage, validate"]
        S3 -.->|Read original using record reference| W
        W --> DB["Amazon DynamoDB<br/>Results, status, versions, token usage"]
        DB --> DS["DynamoDB Streams"]
        DS --> R["AWS Lambda<br/>Policy and routing"]
        R -->|Review needed: create or update case| CASE["Support integration<br/>Department case queue"]
        CASE -->|Case saved: ID, route, urgency, link| SNS["Amazon SNS<br/>Department topics"]
        SNS --> EMAIL["Department email<br/>Urgency + secure case link"]
        R -->|requires_human=false AND policy eligible| AUTOQ["Amazon SQS<br/>Routine handling queue"]
        Q -->|Retry budget exhausted| DLQ["Amazon SQS<br/>Dead-letter queue"]
    end
    subgraph Local["Other approved in-country components"]
        MODEL["Self-hosted or approved local<br/>screening and generation endpoints"]
        ANSWER["Answering service<br/>Draft mode initially"]
        RECOVERY["Manual recovery / support"]
    end
    W <-->|Masked inputs and model results over TLS| MODEL
    AUTOQ --> ANSWER
    DLQ --> RECOVERY

    classDef storage fill:#e9f3df,stroke:#528329,color:#17230e;
    classDef compute fill:#fff1dd,stroke:#c76b13,color:#442500;
    classDef messaging fill:#f5e9fb,stroke:#8b3bb0,color:#361344;
    classDef generic fill:#eef2f6,stroke:#657587,color:#172635;
    class S3,DB storage;
    class W,R compute;
    class EB,Q,DS,SNS,AUTOQ,DLQ messaging;
    class CASE,EMAIL,MODEL,ANSWER,RECOVERY generic;
```

1. **Ingest and buffer.** Store each incoming record in S3. Object-created
   events go through EventBridge to SQS, carrying a record reference rather
   than the narrative. Lambda consumes the queue with bounded concurrency;
   the queue absorbs bursts while respecting local model capacity.
   [S3 event destinations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html),
   [SQS/Lambda processing](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html).
2. **Process and persist.** The worker masks identifiers locally before any
   model call, screens for injection, generates and validates triage, then saves
   the decision and processing state. Screening failures or invalid responses
   that exhaust model retries produce a saved human-review fallback. Unhandled
   worker failures retry through SQS and eventually enter the dead-letter queue.
3. **Route after a durable result.** DynamoDB Streams invokes a routing Lambda
   on a completed decision. It applies escalation rules, creates the support
   case and then publishes a minimal notification to the category's SNS topic.
   Urgency is included in the notice and case priority. Filter stream events to
   avoid routing again when only delivery metadata changes.
   [DynamoDB Streams and Lambda](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.Lambda.html),
   [SNS email subscriptions](https://docs.aws.amazon.com/sns/latest/dg/sns-email-notifications.html).
4. **Separate routine handling.** Only a false human-review flag plus a validated
   low-risk policy permits the routine queue. An answering service can consume
   this queue, initially producing drafts for approval. Customer-visible
   automatic responses and closure require their own later validation.

Use complaint/version keys, conditional writes and delivery records so retries
do not create duplicate cases or repeat model calls unnecessarily. The support
case queue is authoritative; email is an alert, not proof of case acceptance.
Configure failed stream deliveries for recovery as well as SQS dead letters,
and reconcile stored complaints against completed results and routed cases.

## Monitoring, alerts and scheduled reporting

```mermaid
flowchart LR
    WORKERS["Processing and routing Lambdas"] -->|Sanitized logs, traces, stage metrics| OTEL["OpenTelemetry collector"]
    OTEL --> CW["Amazon CloudWatch<br/>Logs and metrics"]
    QUEUES["SQS backlog / dead letters"] --> CW
    CW --> ALARM["CloudWatch alarms"]
    ALARM --> OPS["Amazon SNS<br/>Operations alerts"]
    OPS --> DEV["Developer / on-call email"]

    SCHEDULE["EventBridge Scheduler<br/>Daily or weekly"] --> REPORT["AWS Lambda<br/>Completion and cost report"]
    DB["DynamoDB<br/>Statuses and model token usage"] -->|Read aggregates| REPORT
    CW -->|Read operational metrics| REPORT
    REPORT --> ARCHIVE["Amazon S3<br/>Aggregate report archive"]
    REPORT --> SUMMARY["Amazon SNS<br/>Report notifications"]
    SUMMARY --> MAIL["Operations / business email<br/>Summary + report link"]
```

Set warning/error severity in compute logs and alert on failure thresholds,
oldest-job age, dead letters and routing-delivery failures. Keep complaint text,
model prompts/responses and secrets out of logs and traces. Daily/weekly reports
summarize completed, failed, deferred and outstanding jobs, retries, latency,
model calls, input/output tokens and estimated spend. Missing usage remains
explicitly unknown. The reporting Lambda uses aggregated records; it does not
email narratives. Scheduling uses an
[EventBridge Scheduler Lambda target](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets.html).

## Controls applying to both diagrams

AWS service and region availability, model hosting, telemetry, backups, support
access and email delivery must all satisfy PayGuard's in-country requirements.
If a component cannot meet them, replace it with an approved domestic equivalent;
do not assume a nearby region or a global model API is acceptable. Configure TLS,
encryption at rest, least-privilege IAM roles, protected keys and approved
retention/lifecycle policies. Masking complements these controls and does not
replace residency approval. Human-review rollout gates and rollback behavior
remain those in the production memo.
