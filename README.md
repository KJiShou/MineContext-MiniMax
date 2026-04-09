<div align="center">

<picture>
  <img alt="MineContext" src="src/MineContext-Banner.svg" width="100%" height="auto">
</picture>

### MineContext: Context-Aware AI Companion

An open-source, proactive context-aware AI partner that captures your digital world through screen monitoring and delivers intelligent insights.

Forked from [volcengine/MineContext](https://github.com/volcengine/MineContext) · Enhanced with MiniMax VLM and local Ollama embedding.

[中文](README_zh.md) / English

[![license](https://img.shields.io/badge/license-apache%202.0-white?style=flat-square)](LICENSE)

</div>

<br>

# 👋🏻 What is MineContext

MineContext is a proactive context-aware AI companion that:

- **Captures** your digital world through screen monitoring
- **Understands** content with vision language models
- **Delivers** intelligent insights, summaries, and todos proactively

Think of it as having a second brain that watches your screen, learns from your activities, and reminds you of what matters.

## Key Features

1. **📥 Effortless Collection** - Automatically captures context from your screen
2. **🚀 Proactive Delivery** - Pushes insights, summaries, and todos to your homepage
3. **💡 Intelligent Resurfacing** - Surfaces relevant context when you need it
4. **🔒 Privacy-First** - All data stored locally, embedding models run on your machine

# 🔏 Privacy Protection

## Local-First Architecture

All data is stored locally by default:
- **macOS**: `~/Library/Application Support/MineContext/Data`
- **Windows**: `%APPDATA%\MineContext\Data`

## Local Embedding with Ollama

This fork uses **Ollama** to run embedding models locally. Your context data never leaves your machine for embedding generation - no API calls to third-party embedding services needed.

# 🏁 Quick Start

## 1. Installation

Download from [GitHub Releases](https://github.com/KJiShou/MineContext/releases) or build from source.

## 2. Configure AI Models

MineContext requires two types of AI models:

| Model Type | Purpose | Recommended |
|-----------|---------|-------------|
| **VLM** (Vision Language Model) | Screenshot analysis & understanding | MiniMax |
| **Embedding Model** | Semantic search & context retrieval | Ollama bge-m3 |

### Recommended: MiniMax VLM + Ollama bge-m3

This combination offers:
- **MiniMax VLM**: Best-in-class vision understanding at low cost
- **Ollama bge-m3**: State-of-the-art embedding, running 100% locally

### Setup Ollama (Embedding Model)

**Install Ollama:**

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: Download from https://ollama.com/download
```

**Start Ollama:**
```bash
ollama serve
```

**Download bge-m3 model:**
```bash
ollama pull bge-m3
```

**Verify installation:**
```bash
curl http://localhost:11434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "bge-m3", "input": "hello world"}'
```

### Configure in App

1. Launch MineContext
2. Go to **Settings**
3. Select **MiniMax** as the model platform
4. Enter your MiniMax API key (from [platform.minimaxi.io](https://platform.minimax.io/user-center/payment/token-plan))
5. Select a VLM model (e.g., **MiniMax-M2.7**)
6. **Enable "Use custom embedding model"**
7. Fill in embedding details:
   - **Model name**: `bge-m3`
   - **Base URL**: `http://localhost:11434/v1`
   - **API Key**: Any string (Ollama doesn't require auth - use `ollama`)
8. Click **Save**

## 3. Start Recording

1. Go to **Screen Monitor**
2. Enable screen sharing permissions
3. Set your screen capture area in **Settings**
4. Click **Start Recording**

## 4. Forget It

MineContext works in the background. Your context will be collected gradually. Focus on your work - MineContext will generate todos, insights, and summaries for you.

# 🔧 Backend Debugging

Access the debug console at `http://localhost:1733`:

- View token consumption
- Configure automated task intervals
- Adjust system prompts

# 📐 Architecture

MineContext uses a modular architecture:

```
opencontext/
├── context_capture/    # Screen monitoring, document monitoring
├── context_processing/ # Chunking, entity extraction, merging
├── context_consumption/# Content generation
├── storage/            # SQLite + ChromaDB
├── llm/               # LLM integration (OpenAI-compatible)
└── server/            # FastAPI REST API + WebSocket

frontend/
├── src/main/          # Electron main process
├── src/preload/       # Secure IPC bridge
└── src/renderer/     # React UI
```

## Running from Source

```bash
# Build backend
uv sync
./build.sh

# Install frontend deps
cd frontend
pnpm install

# Development mode
pnpm dev

# Package
pnpm build:mac   # macOS
```

# 📃 License

Apache 2.0 - See [LICENSE](LICENSE)

---

**Star History**

[![Star History Chart](https://api.star-history.com/svg?repos=KJiShou/MineContext&type=Timeline)](https://www.star-history.com/#KJiShou/MineContext&Timeline)
