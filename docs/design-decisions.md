# Architecture Design Decisions

Here is a breakdown of the key technical choices made during the design of this pipeline.

### 1. Why S3 Pre-signed POST instead of uploading through API Gateway?
*   **Decision:** Clients request a pre-signed POST policy from API Gateway, which they use to upload images directly to Amazon S3.
*   **Rationale:** API Gateway has a payload limit of 10MB. Passing large image files through Lambda/API Gateway increases compute costs and latency. Pre-signed POST policies offload data transfer directly to S3, making the architecture highly scalable and cost-effective. We include a `content-length-range` condition in the policy to strictly enforce the 10MB limit at the edge.

### 2. Why Amazon SQS instead of triggering Step Functions directly from S3?
*   **Decision:** S3 event notifications are routed to an Amazon SQS queue, which is then polled by a Lambda function to trigger Step Functions.
*   **Rationale:** S3 events can trigger thousands of times per second. Triggering Step Functions directly might hit AWS service quotas or overwhelm downstream services. SQS acts as a shock absorber. The Dead Letter Queue (DLQ) ensures no image is lost if processing fails after **5 attempts**.

### 3. Why AWS Step Functions instead of a single Lambda function?
*   **Decision:** The processing logic (`Validate` → `Resize` → `Watermark` → `Extract Metadata` → `Store`) is orchestrated using AWS Step Functions.
*   **Rationale:** A single "monolithic" Lambda would be hard to debug, prone to timeouts on large images, and difficult to retry specific steps. Step Functions provides a visual workflow, allows individual steps to have dedicated bounded retry logic (transient errors only), and separates concerns. 

### 4. Why CloudFront with Origin Access Control (OAC)?
*   **Decision:** Processed images are served via CloudFront, and the S3 destination bucket is entirely private.
*   **Rationale:** OAC is the modern AWS best practice for securing S3 origins. It ensures users cannot bypass CloudFront and access the S3 bucket directly. CloudFront also provides edge caching, reducing latency for global users.

### 5. How do we handle Idempotency and Concurrency?
*   **Decision:** The Poller Lambda uses a dedicated `PollerLockTable` in DynamoDB to acquire a 60-second time-based lease (`LeaseExpiry`) and generates a unique `AttemptId` before starting Step Functions. 
*   **Rationale:** SQS guarantees at-least-once delivery, meaning duplicates can happen. The lease prevents concurrent invocations from processing the same file simultaneously. If a Lambda crashes, the lease expires, allowing safe recovery. Every status update (Success/Failure) is strictly conditional on the `AttemptId` to prevent older, stale invocations from overwriting newer attempts.

### 6. Why S3 Versioning and Processing IDs?
*   **Decision:** S3 Versioning is enabled on the ingest bucket, and the poller strictly rejects events missing a `versionId`. A deterministic `processing_id` (SHA-256 of bucket, key, versionId) is used to namespace all intermediate and final object paths.
*   **Rationale:** Without versioning, uploading a file with the same name would overwrite the old one, and in-flight processing might read corrupted data. The `processing_id` ensures that if the same file is uploaded multiple times, the outputs do not collide or overwrite each other.

### 7. Why no Glacier lifecycle on the Destination Bucket?
*   **Decision:** The destination bucket remains entirely in Standard storage.
*   **Rationale:** CloudFront serves these images to end-users. If objects were transitioned to Glacier, they would require a restore operation (taking hours) before users could view them. To manage costs safely, we apply lifecycle rules only to the *Ingest* bucket to clean up intermediate files and noncurrent versions after 30 days.
