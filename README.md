# Atlassian-Agent-Kit

An open-source **Agentic Integration Framework & Evaluation Harness** for enterprise tools (Jira & Confluence). 

Built to solve the hardest part of Enterprise AI: reliable data abstractions, strict workflow state-machines, and non-deterministic agent evaluation.

## Architecture

```mermaid
graph TD
    User[React Dashboard] -->|REST API| FastAPI[FastAPI Backend]
    FastAPI -->|OAuth 2.0 3LO| Atlassian[Atlassian Cloud APIs]
    FastAPI -->|Read/Write| DB[(PostgreSQL)]
    FastAPI -->|Tool Schemas| LLM[Groq / OpenAI LLMs]
    
    subgraph Eval Harness
        FastAPI -->|Trigger| Runner[Eval Runner]
        Runner -->|Judge| LLM
        Runner -->|Persist Results| DB
    end