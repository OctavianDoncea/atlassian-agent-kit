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

## Plugin Architecture
Integrations are plugins. Add one without touching core code:
1. `make new-plugin name=github` (scaffolds `plugins/github.py`)
2. Implement `tools()` (pydantic input models + handlers) and `create_client()`
3. `pytest tests/test_plugin_contract.py` — the generic contract suite validates schema validity, tool-name uniqueness and dispatch
Discovery channels: `src/agentkit/plugins/builtin/*`, drop-in files in `plugins/`, and pip entry-points:
```toml
[project.entry-points."agentkit.plugins"]
github = "my_pkg.plugins:GithubPlugin"