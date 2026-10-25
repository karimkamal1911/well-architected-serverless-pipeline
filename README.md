# 🖼️ Well-Architected AWS Serverless Image Processing Pipeline

![AWS](https://img.shields.io/badge/AWS-Serverless-FF9900?style=flat-square&logo=amazon-aws)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat-square&logo=github-actions)
![Status](https://img.shields.io/badge/Status-Portfolio_Project-success)

> 🌟 **Note:** This project serves as my capstone portfolio for the **AWS Certified Solutions Architect – Associate (SAA-C03)** certification, demonstrating the practical application of AWS Well-Architected principles.

## 📖 Overview
This repository contains the architectural design, application code, and Infrastructure as Code (IaC) for a highly scalable, fully serverless image processing pipeline on AWS.

The system securely accepts image uploads via pre-signed URLs (secured by API Keys, CORS, and throttling), decouples ingestion from processing using Amazon SQS, and orchestrates a multi-step workflow (validation, resizing, watermarking, and metadata extraction) using AWS Step Functions. Final images are delivered globally with low latency via Amazon CloudFront, while metadata is stored in DynamoDB.

## 🏗️ Architecture Diagram
![Architecture Diagram](docs/architecture-diagram.svg)

## 🔄 Architectural Flow
1. **Upload & Initiation:** The client requests a pre-signed URL via API Gateway (secured with API Keys, CORS, and throttling). A Lambda function generates the URL, allowing the client to upload the image directly to the **S3 Ingest Bucket** (bypassing API Gateway payload limits).
2. **Ingest & Buffer:** The S3 upload (filtered to the `uploads/` prefix and protected by S3 Versioning) triggers an event notification that sends a message to an **Amazon SQS** queue. Failed messages are routed to a Dead Letter Queue (DLQ) after 5 failed attempts.
3. **Orchestration & Idempotency:** A **Poller Lambda** reads the SQS message and extracts the `versionId`. It uses a DynamoDB conditional write to acquire an atomic time-based lease (preventing infinite deadlocks from crashed invocations). It generates a deterministic `processing_id` from the bucket, key, and versionId to guarantee that distinct uploads of the same file are processed independently.
4. **Processing Workflow:** Step Functions orchestrates a 5-step microservice pipeline using **AWS Lambda** (equipped with `Pillow` via Lambda Layers):
   * `Validate` → `Resize` → `Watermark` → `Extract Metadata` → `Store`.
   * The `Validate` step uses `ContentLength` checks, deep image inspection (`Image.verify()`), and reads the *exact* S3 version ID provided by the event.
   * All intermediate and final keys are namespaced under `{processing_id}/` to prevent overwriting between versions.
5. **Storage & Delivery:** Processed images are saved to the **S3 Destination Bucket** (standardized to `.jpg`), while metadata is written to **Amazon DynamoDB** keyed by `processing_id`. Images are served globally via **Amazon CloudFront** (secured with OAC) and are kept in Standard storage to guarantee immediate viewer accessibility.
6. **Observability & Alerting:** The system uses **AWS X-Ray** for distributed tracing. **Amazon CloudWatch** monitors for DLQ depth, failed Step Functions executions, and individual Lambda execution errors for the Poller, Validate, Resize, Watermark, and Store functions. **Amazon SNS** sends immediate email alerts if a workflow fails, a message reaches the DLQ, or a Lambda crashes.

## 📂 Repository Structure
This project follows a **Microservice Architecture** to ensure isolated dependencies and least-privilege IAM roles.

```text
├── .github/                # CI/CD pipeline (Validates IaC and runs unit tests)
├── docs/                   # Architecture diagram and detailed design decisions
├── infrastructure/         # Infrastructure as Code (AWS SAM template)
├── layers/                 # Lambda Layers (Pillow dependencies)
├── src/                    # Application code
│   ├── generate_url/       # Pre-signed URL generator microservice
│   ├── poller/             # SQS to Step Functions trigger with DynamoDB locking
│   └── steps/              # Step Functions processing microservices
│       ├── validate/       # Checks file size, format, and pixel limits
│       ├── resize/         # Resizes image (uses Pillow layer)
│       ├── watermark/      # Applies watermark and standardizes to .jpg
│       ├── extract_metadata/ # Extracts image properties
│       └── store/          # Saves final image to S3 and DynamoDB
├── statemachine/           # Step Functions Amazon States Language (ASL) definition
├── tests/                  # Automated unit tests for all Lambda handlers
└── README.md
```

## 🚀 CI/CD Pipeline
This repository uses **GitHub Actions** to ensure code quality. On every push to the `main` branch, the pipeline automatically:
1. Installs all Python dependencies across the microservices and layers.
2. Runs comprehensive automated unit tests for the Poller and all processing Lambdas (and explicitly fails the build if zero tests are discovered using `pipefail` and stream capture).
3. Validates the Infrastructure as Code (IaC) template syntax using the AWS SAM CLI (`sam validate --lint`).
4. Runs `sam build` to verify the Lambda packages and Pillow layers compile successfully.
*(Note: Actual AWS deployment is intentionally bypassed in this demo to avoid requiring AWS credentials and potential charges).*

## 🧠 Design Decisions
*   **Dual DynamoDB Records:** The Poller Lambda maintains an **idempotency lock** record in a dedicated `PollerLockTable` keyed by `processing_id`. Separately, the `Store` Lambda writes a **metadata completion** record to `ImageMetadataTable` keyed by the same `processing_id`. This prevents duplicate processing while maintaining a clean data model.
*   **Lease Locking:** To prevent concurrent invocations from processing the same file while also surviving Lambda crashes, the poller assigns a 60-second lease (`LeaseExpiry`). If a process crashes, the lease expires, and a duplicate SQS message can safely reacquire the lock.
*   **S3 Versioning:** The idempotency key strictly relies on the S3 `versionId` (falling back to `null` only if versioning is disabled). This ensures uploading the same image content to the same key multiple times triggers the pipeline correctly.
*   **CloudFront Compatibility:** The destination bucket intentionally does not transition objects to Glacier. This ensures all images remain immediately retrievable by CloudFront viewers without requiring a restore operation.

## 🔒 Well-Architected Framework Alignment
*   **Operational Excellence:** Infrastructure as Code (IaC), automated CI/CD validation, comprehensive unit testing, X-Ray tracing, and granular CloudWatch alarms.
*   **Security:** Least Privilege IAM policies, API Keys with Usage Plans, CORS (S3 and API Gateway), S3 Block Public Access, AES-256 encryption, CloudFront OAC, and deep image verification.
*   **Reliability:** SQS buffering, atomic DynamoDB time-based lease locking, Step Functions exponential backoff, Dead Letter Queues (DLQ), and SNS failure alerts.
*   **Performance:** Pre-signed URLs offload ingestion directly to S3, and CloudFront caches processed images at the edge.
*   **Cost Optimization:** Serverless pay-per-use pricing.
*   **Sustainability:** Serverless compute (Lambda) scales to zero when idle, minimizing wasted energy, and CloudFront edge caching reduces the energy required to transmit data over long distances.

---
**License:** This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
