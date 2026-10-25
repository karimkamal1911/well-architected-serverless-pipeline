# 🖼️ Well-Architected AWS Serverless Image Processing Pipeline

![AWS](https://img.shields.io/badge/AWS-Serverless-FF9900?style=flat-square&logo=amazon-aws)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat-square&logo=github-actions)
![Status](https://img.shields.io/badge/Status-Portfolio_Project-success)

> 🌟 **Note:** This project serves as my capstone portfolio for the **AWS Certified Solutions Architect – Associate (SAA-C03)** certification.

## 📖 Overview
This repository contains a highly scalable, fully serverless image processing pipeline on AWS. It securely accepts image uploads via pre-signed POST policies, decouples ingestion using Amazon SQS, and orchestrates processing using AWS Step Functions. Final images are delivered globally via Amazon CloudFront.

## 🔄 Architectural Flow
1. **Upload & Initiation:** Client requests a pre-signed POST policy via API Gateway (secured with API Keys, CORS, and throttling). A Lambda generates the policy with a `content-length-range` (10MB max), allowing direct upload to the **S3 Ingest Bucket**.
2. **Ingest & Buffer:** The S3 upload (filtered to `uploads/` and protected by Versioning) triggers an event to **SQS**. Failed messages go to a DLQ.
3. **Orchestration:** A **Poller Lambda** extracts the `versionId`. It strictly rejects missing version IDs. It uses a DynamoDB time-based lease to atomically lock the `processing_id`, then starts Step Functions.
4. **Processing Workflow:** Step Functions executes `Validate → Resize → Watermark → Extract Metadata → Store`. 
   * All intermediate/final keys are namespaced under `{processing_id}/`.
   * `Validate` reads the exact `VersionId` from the event.
   * Error handling uses `ResultPath: "$.error"` to preserve the original state context.
5. **Storage & Delivery:** Processed images are saved to the **S3 Destination Bucket** (standardized to `.jpg`). Metadata goes to **DynamoDB**. The `Store` step updates the lock to `SUCCEEDED`. Images are served via **CloudFront** (OAC secured) and kept in Standard storage.
6. **Observability:** **X-Ray** tracing, **CloudWatch** alarms (DLQ, SFN fails, Lambda errors), and **SNS** alerts.

## 🧠 Design Decisions
*   **Dual DynamoDB Records:** The Poller maintains an **idempotency lock** (`PollerLockTable`). The `Store` Lambda writes a **completion metadata** record (`ImageMetadataTable`). 
*   **Lease Locking:** The poller assigns a 60-second lease (`LeaseExpiry`). A crashed process's lease expires, allowing safe reacquisition without relying on duplicate S3 events.
*   **S3 Versioning Enforcement:** Missing `versionId` is rejected. Processing relies entirely on the specific source version, avoiding overwrites.
*   **Upload Security:** Presigned POST policies enforce `content-length-range` at the edge. API keys provide throttling/usage identification (not full authentication).
*   **Storage Lifecycle:** The ingest bucket expires noncurrent versions and intermediate objects after 30 days, while the destination bucket remains immediately accessible without Glacier transitions.

## 🔒 Well-Architected Framework Alignment
*   **Operational Excellence:** IaC, automated CI/CD validation, comprehensive unit testing, X-Ray, CloudWatch alarms.
*   **Security:** Least Privilege IAM, API Keys, CORS, Block Public Access, AES-256, CloudFront OAC, deep image verification.
*   **Reliability:** SQS buffering, DynamoDB atomic lease locking, Step Functions error catching (with state preservation), DLQs, SNS alerts.
*   **Performance:** Pre-signed POST offloads ingestion, CloudFront caches at edge.
*   **Cost Optimization:** Serverless pay-per-use, S3 Lifecycle cleanup.
*   **Sustainability:** Scale-to-zero architecture.

---
**License:** This project is licensed under the Apache License 2.0.
