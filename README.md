# 🖼️ Well-Architected AWS Serverless Image Pipeline

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Serverless](https://img.shields.io/badge/Serverless-FD5750?style=for-the-badge&logo=serverless&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

> 🌟 **Note:** This project serves as my capstone portfolio for the AWS Certified Solutions Architect – Associate (SAA-C03) certification, demonstrating best practices across the AWS Well-Architected Framework.

## 📖 Overview
This repository contains the architectural design, application code, and design documentation for a highly scalable, fully serverless image processing pipeline on AWS. 

The system securely accepts image uploads, buffers them to handle traffic spikes, orchestrates a multi-step processing workflow (validation, resizing, watermarking), and delivers the final images globally with low latency.

## 🏗️ Architecture Diagram

![Architecture Diagram](docs/architecture-diagram.png)

## ✨ Architectural Highlights
*   **Event-Driven & Decoupled:** Uses Amazon SQS to decouple S3 ingestion from processing, preventing Lambda throttling during traffic spikes.
*   **State Orchestration:** Utilizes AWS Step Functions to manage the processing pipeline, ensuring each step has custom retry logic and error handling (DLQ).
*   **Secure by Design:** Employs API Gateway, AWS WAF (rate limiting), and S3 Pre-signed URLs for secure, direct-to-cloud uploads.
*   **Global Delivery:** Uses Amazon CloudFront with Origin Access Control (OAC) to serve images securely with low latency.
*   **Cost-Optimized:** S3 Lifecycle policies automatically transition older processed images to Glacier Instant Retrieval and Deep Archive.

## 📂 Repository Structure
*   `/docs`: Contains the architecture diagram and detailed design decisions.
*   `/src`: Contains the Python source code for the core Lambda functions.
*   `/.github`: Contains the CI/CD deployment workflow.

## 💡 Design Decisions
For a deep dive into *why* specific AWS services were chosen (e.g., SQS vs. Kinesis, Step Functions vs. monolithic Lambda), please read the [Design Decisions Document](docs/design-decisions.md).

## 🔒 Well-Architected Framework Alignment
*   **Security:** IAM Least Privilege, WAF integration, S3 Block Public Access, and CloudFront OAC.
*   **Reliability:** SQS buffering, Step Functions exponential backoff retries, and Dead Letter Queues (DLQ).
*   **Performance:** Pre-signed URLs offload ingestion directly to S3, and CloudFront caches processed images at the edge.
