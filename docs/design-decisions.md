# Architecture Design Decisions

Here is a breakdown of the key technical choices made during the design of this pipeline.

### 1. Why S3 Pre-signed URLs instead of uploading through API Gateway?
**Decision:** Clients request a pre-signed URL from API Gateway, which they use to upload images directly to Amazon S3.
**Rationale:** API Gateway has a payload limit of 10MB. Passing large image files through Lambda/API Gateway increases compute costs and latency. Pre-signed URLs offload data transfer directly to S3, making the architecture highly scalable and cost-effective.

### 2. Why Amazon SQS instead of triggering Step Functions directly from S3?
**Decision:** S3 event notifications are routed to an Amazon SQS queue, which is then polled by a Lambda function to trigger Step Functions.
**Rationale:** S3 events can trigger thousands of times per second. Triggering Step Functions directly might hit AWS service quotas or overwhelm downstream services. SQS acts as a shock absorber. The Dead Letter Queue (DLQ) ensures no image is lost if processing fails after 3 attempts.

### 3. Why AWS Step Functions instead of a single Lambda function?
**Decision:** The processing logic (Validate -> Resize -> Watermark -> Extract Metadata) is orchestrated using AWS Step Functions.
**Rationale:** A single "monolithic" Lambda would be hard to debug, prone to timeouts on large images, and difficult to retry specific steps. Step Functions provides a visual workflow, allows individual steps to have dedicated retry logic, and separates concerns.

### 4. Why CloudFront with Origin Access Control (OAC)?
**Decision:** Processed images are served via CloudFront, and the S3 destination bucket is entirely private.
**Rationale:** OAC is the modern AWS best practice for securing S3 origins. It ensures users cannot bypass CloudFront and access the S3 bucket directly. CloudFront also provides edge caching, reducing latency for global users.
