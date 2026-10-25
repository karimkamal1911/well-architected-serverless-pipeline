# 🖼️ Well-Architected AWS Serverless Image Processing Pipeline

![AWS](https://img.shields.io/badge/AWS-Serverless-FF9900?style=flat-square&logo=amazon-aws)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat-square&logo=github-actions)
![Status](https://img.shields.io/badge/Status-Portfolio_Project-success)

> 🌟 **Note:** This project serves as my capstone portfolio for the **AWS Certified Solutions Architect – Associate (SAA-C03)** certification, demonstrating the practical application of AWS Well-Architected principles.

## 📖 Overview
This repository contains the architectural design, application code, and Infrastructure as Code (IaC) for a highly scalable, fully serverless image processing pipeline on AWS.

The system securely accepts image uploads via pre-signed POST policies (secured by API Keys, CORS, and enforced content-length constraints), decouples ingestion from processing using Amazon SQS, and orchestrates a multi-step workflow using AWS Step Functions. Final images are delivered globally with low latency via Amazon CloudFront.

## 🏗️ Architecture Diagram
![Architecture Diagram](docs/architecture-diagram.svg)

## 🔄 Architectural Flow
1. **Upload & Initiation:** The client requests a pre-signed POST policy via API Gateway (secured with API Keys, CORS, and throttling). A Lambda function generates the policy with a `content-length-range` condition (max 10MB), allowing the client to upload the image directly to the **S3 Ingest Bucket**.
2. **Ingest & Buffer:** The S3 upload (filtered to `uploads/` and protected by Versioning) triggers an event notification to an **Amazon SQS** queue. Failed messages are routed to a Dead Letter Queue (DLQ) after 5 attempts.
3. **Orchestration & Idempotency:** A **Poller Lambda** extracts the `versionId` (rejecting events without one). It uses a DynamoDB conditional write to acquire a time-based lease and assigns a unique `AttemptId`. It safely handles ambiguous `StartExecution` outcomes by relying on SQS redelivery and `DescribeExecution` to reconcile state without prematurely deleting locks.
4. **Processing Workflow:** Step Functions orchestrates a 5-step microservice pipeline using **AWS Lambda** (equipped with `Pillow` via Lambda Layers):
   * `Validate` → `Resize` → `Watermark` → `Extract Metadata` → `Store`.
   * The `Validate` step captures the S3 `LastModified` timestamp to track the original `upload_time`, checks `ContentLength`, and performs deep image inspection (`Image.verify()`).
   * All intermediate and final keys are namespaced under `{processing_id}/` to prevent overwriting between versions.
5. **Storage & Delivery:** Processed images are saved to the **S3 Destination Bucket** (standardized to `.jpg`), while metadata is written to **Amazon DynamoDB**. The metadata record includes both the original `UploadTime` and the processing `Timestamp`. The `Store` step updates the lock to `SUCCEEDED`.
6. **Observability & Alerting:** The system uses **AWS X-Ray** for distributed tracing. **Amazon CloudWatch** monitors for DLQ depth, failed Step Functions executions, and individual Lambda execution errors. **Amazon SNS** sends immediate email alerts for both successful completions and failures, serialized as JSON strings for easy parsing.

## 📂 Repository Structure
This project follows a **Microservice Architecture** to ensure isolated dependencies and least-privilege IAM roles.

├── .github/                # CI/CD pipeline (Validates IaC and runs unit tests)
├── docs/                   # Architecture diagram and detailed design decisions
├── infrastructure/         # Infrastructure as Code (AWS SAM template)
├── layers/                 # Lambda Layers (Pillow dependencies)
├── src/                    # Application code
│   ├── generate_url/       # Pre-signed POST generator microservice
│   ├── poller/             # SQS to Step Functions trigger with DynamoDB locking
│   └── steps/              # Step Functions processing microservices
│       ├── validate/       # Checks file size, format, pixel limits, captures timestamp
│       ├── resize/         # Resizes image (uses Pillow layer)
│       ├── watermark/      # Applies watermark and standardizes to .jpg
│       ├── extract_metadata/ # Extracts image properties
│       └── store/          # Saves final image to S3 and metadata to DynamoDB
├── statemachine/           # Step Functions Amazon States Language (ASL) definition
├── tests/                  # Automated unit tests for all Lambda handlers
└── README.md

## 🚀 CI/CD Pipeline
This repository uses GitHub Actions to ensure code quality. On every push to the main branch, the pipeline automatically:

Installs all Python dependencies across the microservices and layers.

Runs comprehensive automated unit tests for the Poller and all processing Lambdas (and explicitly fails the build if zero tests are discovered).

Validates the Infrastructure as Code (IaC) template syntax using the AWS SAM CLI (sam validate --lint).

Runs sam build to verify the Lambda packages and Pillow layers compile successfully.

(Note: Actual AWS deployment is intentionally bypassed in this demo to avoid requiring AWS credentials and potential charges).

## 🧠 Design Decisions

Dual DynamoDB Records: The Poller Lambda maintains an idempotency lock record in a dedicated PollerLockTable keyed by processing_id. Separately, the Store Lambda writes a metadata completion record to ImageMetadataTable.

Metadata Timestamps: The Store step records UploadTime (derived from the S3 LastModified metadata) alongside Timestamp (the processing completion time) to provide exact lineage data.

Lease Locking & Ambiguity Handling: The poller assigns a 60-second lease (LeaseExpiry) and a unique AttemptId. If a process crashes or StartExecution times out ambiguously, the lease expires, allowing SQS redelivery to safely inspect the existing execution state via DescribeExecution before deciding whether to retry or reconcile.

Bounded Retries & Terminal Failures: Step Functions retries transient task failures up to 3 times with exponential backoff. If the workflow ultimately fails, it marks the lock FAILED and alerts via SNS. Whole-workflow automatic retries are not used to prevent infinite loops; a failed execution must be manually replayed.

State Preservation on Failure: Step Functions Catch blocks use ResultPath: "$.error" to preserve the original input context. The MarkFailed state uses ResultPath: null to ensure the SNS notification includes both the original error and the image/attempt identifiers.

S3 Versioning Enforcement: Missing versionId is strictly rejected. Processing relies entirely on the specific source version, avoiding overwrites. Intermediate and final object paths are namespaced under {processing_id}/.

Upload Security: Presigned POST policies enforce content-length-range at the edge. API keys provide throttling/usage identification (not full authentication).

Storage Lifecycle: The ingest bucket expires current uploads, intermediate objects, and noncurrent versions after 30 days, and aborts incomplete multipart uploads after 7 days. The destination bucket remains immediately accessible without Glacier transitions.

## 🔒 Well-Architected Framework Alignment

Operational Excellence: Infrastructure as Code (IaC), automated CI/CD validation, comprehensive unit testing, X-Ray tracing, and granular CloudWatch alarms.

Security: Least Privilege IAM policies, API Keys, CORS, S3 Block Public Access, AES-256 encryption, CloudFront OAC, and deep image verification.

Reliability: SQS buffering, atomic DynamoDB time-based lease locking, Step Functions ResultPath context preservation, bounded exponential backoff, DLQs, and SNS alerts.

Performance: Pre-signed URLs offload ingestion, CloudFront caches images at the edge.

Cost Optimization: Serverless pay-per-use pricing and automated S3 lifecycle cleanup.

Sustainability: Serverless compute (Lambda) scales to zero when idle, minimizing wasted energy, and CloudFront edge caching reduces the energy required to transmit data over long distances.

## 📄 License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
