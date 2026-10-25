# 🖼️ Well-Architected AWS Serverless Image Processing Pipeline

![AWS](https://img.shields.io/badge/AWS-Serverless-FF9900?style=flat-square&logo=amazon-aws)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat-square&logo=github-actions)
![Status](https://img.shields.io/badge/Status-Portfolio_Project-success)

> 🌟 **Note:** This project serves as my capstone portfolio for the **AWS Certified Solutions Architect – Associate (SAA-C03)** certification, demonstrating deep expertise across all six pillars of the AWS Well-Architected Framework.

## 📖 Overview
This repository contains the architectural design, application code, and Infrastructure as Code (IaC) for a highly scalable, fully serverless image processing pipeline on AWS.

The system securely accepts image uploads using pre-signed URLs, decouples ingestion from processing using Amazon SQS, and orchestrates a multi-step workflow (validation, resizing, watermarking, and metadata extraction) using AWS Step Functions. Final images are delivered globally with low latency via Amazon CloudFront, while metadata is stored in DynamoDB.

## 🏗️ Architecture Diagram
![Architecture Diagram](docs/architecture-diagram.svg)

## 🔄 Architectural Flow
1. **Upload & Initiation:** The client requests a pre-signed URL via API Gateway (protected by AWS WAF rate-limiting). A Lambda function generates the URL, allowing the client to upload the image directly to the **S3 Ingest Bucket** (bypassing API Gateway payload limits).
2. **Ingest & Buffer:** The S3 upload triggers an event notification that sends a message to an **Amazon SQS** queue, complete with a Dead Letter Queue (DLQ) for failed messages.
3. **Orchestration:** A **Poller Lambda** reads the SQS message and starts an **AWS Step Functions** execution. 
4. **Processing Workflow:** Step Functions orchestrates a 5-step microservice pipeline using **AWS Lambda** (equipped with `Pillow` via Lambda Layers):
   * `Validate` → `Resize` → `Watermark` → `Extract Metadata` → `Store`.
5. **Storage & Delivery:** Processed images are saved to the **S3 Destination Bucket**, while metadata is written to **Amazon DynamoDB**. Users retrieve images globally via **Amazon CloudFront** (secured with Origin Access Control).
6. **Notifications & Observability:** The system uses **Amazon SNS** for Success/Failure email alerts, **Amazon CloudWatch** for metrics and DLQ alarms, and **AWS X-Ray** for distributed tracing.

## 📂 Repository Structure
This project follows a **Microservice Architecture** to ensure isolated dependencies and least-privilege IAM roles.

```text
├── .github/                # CI/CD pipeline (Validates IaC and builds dependencies)
├── docs/                   # Architecture diagram and detailed design decisions
├── infrastructure/         # Infrastructure as Code (AWS SAM template)
├── src/                    # Application code
│   ├── generate_url/       # Pre-signed URL generator microservice
│   ├── poller/             # SQS to Step Functions trigger microservice
│   └── steps/              # Step Functions processing microservices
│       ├── validate/       # Checks image format and validity
│       ├── resize/         # Resizes image (uses Pillow layer)
│       ├── watermark/      # Applies watermark (uses Pillow layer)
│       ├── extract_metadata/ # Extracts image properties
│       └── store/          # Saves final image to S3 and DynamoDB
├── statemachine/           # Step Functions Amazon States Language (ASL) definition
└── README.md
```

## 🚀 CI/CD Pipeline
This repository uses **GitHub Actions** to ensure code quality. On every push to the `main` branch, the pipeline automatically:
1. Installs all Python dependencies across the microservices.
2. Validates the **AWS SAM** Infrastructure as Code template.
3. Runs `sam build` to verify the Lambda packages compile successfully.
*(Note: The deployment step is intentionally bypassed in this demo to avoid AWS charges).*

## 🔒 Well-Architected Framework Alignment
*   **Operational Excellence:** Infrastructure as Code (IaC), X-Ray tracing, and granular CloudWatch alarms.
*   **Security:** Least Privilege IAM, WAF integration, S3 Block Public Access, SSE-KMS encryption, and CloudFront OAC.
*   **Reliability:** SQS buffering, Step Functions exponential backoff retries, and Dead Letter Queues (DLQ).
*   **Performance:** Pre-signed URLs offload ingestion directly to S3, and CloudFront caches processed images at the edge.
*   **Cost Optimization:** Automated S3 Lifecycle transitions to Glacier, serverless pay-per-use pricing.
*   **Sustainability:** Serverless compute (Lambda) scales to zero when idle, minimizing wasted energy, and CloudFront edge caching reduces the energy required to transmit data over long distances.

---
**License:** This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
