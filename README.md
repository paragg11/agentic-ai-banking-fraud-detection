# Banking Fraud Pattern Detection Agent

An Agentic AI-powered banking fraud detection and investigation system built using Python, LangGraph, Neo4j, GraphRAG, and Large Language Models.

## Project Overview

Traditional fraud detection systems often analyze transactions individually. However, suspicious activities can become more visible when relationships between customers, devices, IP addresses, transactions, and merchants are analyzed together.

This project aims to build an intelligent fraud investigation system using Knowledge Graphs and Agentic AI.

## Key Features

- Transaction ingestion and preprocessing
- Customer and transaction relationship mapping
- Neo4j Knowledge Graph construction
- Graph-based suspicious pattern detection
- GraphRAG-powered investigation and retrieval
- LangGraph-based agent orchestration
- Explainable AI-generated fraud investigation reports
- Interactive fraud investigation dashboard

## Technology Stack

| Category | Technology |
|---|---|
| Programming | Python |
| Agent Framework | LangGraph |
| Graph Database | Neo4j |
| LLM | Amazon Bedrock |
| GraphRAG | LangChain |
| Data Processing | Pandas |
| Machine Learning | Scikit-learn |
| Backend | FastAPI |
| Frontend | Streamlit |
| Version Control | Git and GitHub |

## Knowledge Graph Design

The system will model the following entities:

- Customer
- Transaction
- Device
- IP Address
- Merchant

Example relationships:

```text
Customer → INITIATED → Transaction
Transaction → PAID_TO → Merchant
Customer → USED_DEVICE → Device
Customer → CONNECTED_FROM → IPAddress
Device → USED_BY → Customer
```

## Agent Workflow

1. Transaction ingestion
2. Customer history retrieval
3. Connected device and IP analysis
4. Suspicious transaction pattern detection
5. Graph anomaly analysis
6. Risk scoring
7. LLM-generated investigation explanation

## Development Status

**Current status:** Initial project setup.

This repository will be updated incrementally as each development milestone is completed.

## Dataset and Responsible AI

The initial implementation will use synthetic banking transaction data.

The system is intended for educational and research purposes. Risk indicators are not proof of fraud, and generated explanations will be grounded in retrieved evidence.

No real customer banking information will be included.

## Author

Parag Gunjal

GitHub: https://github.com/paragg11