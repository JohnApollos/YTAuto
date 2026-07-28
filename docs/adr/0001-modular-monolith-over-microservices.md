# 1. Modular Monolith over Microservices

Date: 2026-07-25

## Status
Accepted

## Context
The system involves discrete, heavy computational tasks (downloading, transcribing, LLM evaluation, video rendering, and API uploading). Traditional enterprise architectures often separate these into standalone microservices. However, this project is operated and maintained by a single developer on a single consumer-grade PC.

## Decision
We will build the system as a **Modular Monolith**. The application will live in a single repository and run on a unified tech stack (FastAPI / Python), but with strictly separated internal namespaces (`channels`, `workers`, `runtime`). Communication will happen via a shared Postgres database (and Redis queues for tasks), rather than HTTP APIs between internal components.

## Consequences
- **Positive:** Dramatically reduces operational overhead, deployment complexity, and debugging friction. Single repository means shared types and models.
- **Negative:** We cannot scale individual components horizontally across multiple servers without scaling the entire monolith (though the asynchronous worker queue mitigates this by allowing more worker instances). This is an acceptable tradeoff for a single-PC target architecture.
