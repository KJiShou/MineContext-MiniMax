# MineContext

## Project Setup

### Build Backend

#### for macos

```bash
uv sync
source .venv/bin/activate
./build.sh
```

#### for windows

not support yet

### Install

```bash
cd frontend
pnpm install
```

### Development

```bash
pnpm dev
```

### Build APP

```bash
# For macOS
pnpm build:mac
# Data Path
# ～/Library/Application\ Support/MineContext
```

### Data Path

～/Library/Application\ Support/MineContext

## AI Model Configuration

### Recommended Setup: MiniMax VLM + Ollama bge-m3 Embedding

MineContext uses two AI models working together:
- **Vision Language Model (VLM)**: For screenshot analysis and understanding
- **Embedding Model**: For semantic search and context retrieval

The recommended setup uses MiniMax as VLM and a local Ollama bge-m3 model as embedding.

#### Why This Setup?

- **MiniMax VLM**: Best-in-class vision understanding at low cost
- **Ollama bge-m3**: State-of-the-art embedding model running locally, supports multilingual and multimodal retrieval

#### Backend Configuration (config.yaml)

```yaml
llm:
  provider: minimax
  api_key: "your MiniMax API key"
  base_url: "https://api.minimax.io/v1"
  model: "MiniMax-M2.7"

embedding:
  provider: "custom"
  embedding_base_url: "http://localhost:11434/v1"
  embedding_api_key: "ollama"
  embedding_model_id: "bge-m3"
  embedding_model_platform: "custom"
```

#### Setting Up Ollama (Local Embedding)

**1. Install Ollama**

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: Download from https://ollama.com/download
```

**2. Start Ollama Server**

```bash
ollama serve
```

**3. Pull bge-m3 Model**

```bash
ollama pull bge-m3
```

This downloads the ~1.5GB bge-m3 embedding model. First run may take a few minutes depending on your internet connection.

**4. Verify Ollama is Running**

```bash
curl http://localhost:11434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "bge-m3", "input": "hello world"}'
```

You should receive a JSON response with an embedding vector.

#### Frontend Settings

In the MineContext frontend settings:

1. Select **MiniMax** as the model platform
2. Enter your MiniMax API key (get from https://platform.minimaxi.com/user-center/basic-information/interface-key)
3. Select a VLM model (e.g., MiniMax-M2.7)
4. **Enable "Use custom embedding model"**
5. Fill in the embedding fields:
   - **Model name**: `bge-m3`
   - **Base URL**: `http://localhost:11434/v1`
   - **API Key**: Any string (Ollama doesn't require authentication — use `ollama` as placeholder)
6. Click **Save**

#### Troubleshooting Ollama

**Ollama not starting?**
```bash
# Check if ollama is running
ps aux | grep ollama

# Restart ollama
ollama serve
```

**Model not found?**
```bash
# List installed models
ollama list

# Pull again if missing
ollama pull bge-m3
```

**Connection refused on localhost:11434?**
- Ensure Ollama is running
- Check firewall settings
- Try `curl http://localhost:11434/api/tags` to test connectivity
