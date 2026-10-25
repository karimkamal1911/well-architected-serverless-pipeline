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
1. **Upload & Initiation:** The client requests a pre-signed POST policy via API Gateway (secured with API Keys, CORS, and throttling). A Lambda function generates the policy with a `content-length-range` condition (max 10MB), allowing the client to upload the image directly to the **S3 Ingest Bucket** securely.
2. **Ingest & Buffer:** The S3 upload (filtered to the `uploads/` prefix and protected by S3 Versioning) triggers an event notification that sends a message to an **Amazon SQS** queue. Failed messages are routed to a DLQ after 5 attempts.
3. **Orchestration & Idempotency:** A **Poller Lambda** reads the SQS message and extracts the `versionId`. It strictly enforces the presence of a version ID to guarantee version-safe processing. It uses a DynamoDB conditional write to acquire an atomic time-based lease, generates a deterministic `processing_id`, and starts Step Functions.
4. **Processing Workflow:** Step Functions orchestrates a 5-step microservice pipeline using **AWS Lambda** (equipped with `Pillow` via Lambda Layers):
   * `Validate` → `Resize` → `Watermark` → `Extract Metadata` → `Store`.
   * The `Validate` step uses `ContentLength` checks, deep image inspection (`Image.verify()`), and reads the *exact* S3 version ID provided by the event.
   * All intermediate and final keys are namespaced under `{processing_id}/` to prevent overwriting between versions.
5. **Storage & Delivery:** Processed images are saved to the **S3 Destination Bucket** (standardized to `.jpg`), while metadata is written to **Amazon DynamoDB**. The `Store` step also marks the execution lock as `SUCCEEDED`. Images are served globally via **Amazon CloudFront** (secured with OAC) and are kept in Standard storage to guarantee immediate viewer accessibility.
6. **Observability & Alerting:** The system uses **AWS X-Ray** for distributed tracing. **Amazon CloudWatch** monitors for DLQ depth, failed Step Functions executions, and individual Lambda execution errors. **Amazon SNS** sends immediate email alerts on failures.

## 📂 Repository Structure
```text
├── .github/                # CI/CD pipeline
├── docs/                   # Architecture diagram
├── infrastructure/         # AWS SAM template
├── layers/                 # Pillow Layer
├── src/                    # Application code
│   ├── generate_url/       # Pre-signed POST generator
│   ├── poller/             # SQS -> Step Functions with Lease Locking
│   └── steps/              # Processing microservices
├── statemachine/           # Step Functions ASL definition
├── tests/                  # Automated unit tests
└── README.md
```

## 🚀 CI/CD Pipeline
This repository uses **GitHub Actions** to ensure code quality. On every push to the `main` branch, the pipeline automatically:
1. Installs all Python dependencies.
2. Runs automated unit tests (failing the build if zero tests are discovered).
3. Validates the IaC template (`sam validate --lint`).
4. Runs `sam build`.

*(Note: Actual AWS deployment is intentionally bypassed in this demo).*

## 🧠 Design Decisions
*   **Dual DynamoDB Records:** The Poller Lambda maintains an **idempotency lock** record in a dedicated `PollerLockTable` keyed by `processing_id`. The `Store` Lambda writes a **metadata completion** record to `ImageMetadataTable`. Step Functions marks the lock as `FAILED` upon failure.
*   **Lease Locking:** To prevent concurrent invocations from processing the same file while also surviving Lambda crashes, the poller assigns a 60-second lease (`LeaseExpiry`). If a process crashes, the lease expires, and a duplicate SQS message can safely reacquire the lock.
*   **S3 Versioning Enforcement:** The idempotency key strictly relies on the S3 `versionId`. If an event is missing a `versionId`, the poller rejects it to prevent correctness issues.
*   **Upload Security & Size Enforcement:** Presigned POST policies are used with a `content-length-range` condition to reject oversized files at the edge before they hit the Lambda validator.
*   **API Key Limitations:** The API Key protects against casual abuse and enables usage tracking, but it is not a substitute for full caller authentication (like Cognito). It is securely injected via the `X-Api-Key` header and never embedded in client-side code.
*   **Storage Lifecycle:** The ingest bucket has a lifecycle rule to expire noncurrent versions after 30 days and abort incomplete multipart uploads after 7 days, preventing unbounded storage growth.

## 🔒 Well-Architected Framework Alignment
*   **Operational Excellence:** Infrastructure as Code (IaC), automated CI/CD validation, unit testing, X-Ray tracing, and granular CloudWatch alarms.
*   **Security:** Least Privilege IAM policies, API Keys, CORS, S3 Block Public Access, AES-256 encryption, CloudFront OAC, and deep image verification.
*   **Reliability:** SQS buffering, atomic DynamoDB time-based lease locking, Step Functions exponential backoff, DLQs, and SNS alerts.
*   **Performance:** Pre-signed URLs offload ingestion, CloudFront caches images at the edge.
*   **Cost Optimization:** Serverless pay-per-use pricing.
*   **Sustainability:** Scale-to-zero architecture and edge caching.

---
**License:** This project is licensed under the Apache License 2.0.
