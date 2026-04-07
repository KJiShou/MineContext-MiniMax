# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MineContext is an open-source, proactive context-aware AI partner that captures user context (screenshots, documents, activities) via screen monitoring and provides AI-powered insights, summaries, and todos through a local-first architecture.

**Key Stack**: Python/FastAPI backend + Electron/React/TypeScript frontend

## Development Commands

### Backend (Python)

```bash
# Install dependencies
uv sync

# Run the server
uv run opencontext start --port 1733
uv run opencontext start --config /path/to/config.yaml

# Run tests
cd opencontext && uv pytest tests/tools/ -v

# Run a single test file
uv pytest opencontext/tests/tools/test_minimax_web_search.py -v

# Code formatting
black opencontext/ && isort opencontext/
```

### Frontend (Electron/React)

```bash
cd frontend
pnpm install
pnpm dev          # Development mode
pnpm build:mac    # Build for macOS
```

## Architecture

### Backend Layers (opencontext/)

```
context_capture/    → Screenshot monitoring, document monitoring (extensible via CaptureInterface)
context_processing/ → Document chunking, entity extraction, context merging, multimodal processing
context_consumption/ → Content generation services
managers/           → Business logic: CaptureManager, ProcessorManager, ConsumptionManager
storage/            → Multi-backend: SQLite (documents), ChromaDB (vectors)
llm/               → LLM providers: OpenAI, Doubao, MiniMax via OpenAI-compatible API
tools/             → Tool system with function calling (ToolsExecutor + BaseTool)
server/            → FastAPI REST API + WebSocket
```

### Configuration Priority

Command-line args > config.yaml > environment variables > defaults

### LLM Integration

- `opencontext/llm/llm_client.py` - Core LLM client with chat completions and tool calling
- `opencontext/llm/global_vlm_client.py` - Singleton wrapper for VLM access
- `opencontext/llm/global_embedding_client.py` - Singleton for embeddings
- Providers are OpenAI-compatible; set `provider` in config (openai, doubao, minimax)

### Tool System

Tools follow a `BaseTool` pattern:
- `opencontext/tools/base.py` - Abstract base class
- `opencontext/tools/tools_executor.py` - Executes tools by name mapping
- `opencontext/tools/tool_definitions.py` - Centralized tool schemas
- Tool implementations in `opencontext/tools/operation_tools/`, `retrieval_tools/`, `profile_tools/`

When adding new tools:
1. Create tool class inheriting `BaseTool`
2. Implement `get_name()`, `get_description()`, `get_parameters()`, `execute()`
3. Register in `tool_definitions.py` and `tools_executor.py`

### Storage Backends

- **ChromaDB** (default): Vector similarity search for contexts
- **SQLite**: Document storage (activities, reports, todos)
- **Qdrant** (optional): Alternative vector database

## Key Patterns

### Adding New Context Sources

1. Implement `CaptureInterface` in `context_capture/`
2. Register in `CaptureManager`

### Adding New LLM Providers

1. Ensure OpenAI-compatible API
2. Set `provider`, `base_url`, `api_key`, `model` in config

### Response Schema for Tools

Use standardized `ToolResponse` schema in `opencontext/tools/tool_response.py`:
```python
ToolResponse(status="success"|"error"|"partial", type=str, data=Any,
             confidence=0.0-1.0, cached=bool, error_message=str, summary=str)
```

## Important Paths

- Backend: `opencontext/`
- Frontend: `frontend/`
- Config: `config/config.yaml`
- Architecture docs: `src/architecture-overview.md`
