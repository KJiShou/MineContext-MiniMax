<div align="center">

<picture>
  <img alt="MineContext" src="src/MineContext-Banner.svg" width="100%" height="auto">
</picture>

### MineContext：洞察本质，激发创造

一个开源、主动的上下文感知 AI 伙伴，通过屏幕监控捕获你的数字世界，主动推送智能洞察。

基于 [volcengine/MineContext](https://github.com/volcengine/MineContext) fork · 使用 MiniMax VLM + 本地 Ollama embedding

[中文](README_zh.md) / [English](README.md)

[![license](https://img.shields.io/badge/license-apache%202.0-white?style=flat-square)](LICENSE)

</div>

<br>

# 👋🏻 MineContext 是什么

MineContext 是一个主动式上下文感知 AI 伙伴，能够：

- **捕获** - 通过屏幕监控捕获你的数字世界
- **理解** - 使用视觉语言模型理解内容
- **推送** - 主动向你推送洞察、摘要和待办

就像拥有了一个第二大脑，观看你的屏幕，从你的活动中学习，并在重要时刻提醒你。

## 核心功能

1. **📥 无负担收集** - 自动从屏幕捕获上下文
2. **🚀 主动推送** - 将洞察、摘要和待办推送到首页
3. **💡 智能浮现** - 在你需要时浮现相关上下文
4. **🔒 隐私优先** - 所有数据本地存储，embedding 模型在本地运行

# 🔏 隐私保护

## 本地优先架构

所有数据默认存储在本地：
- **macOS**：`~/Library/Application Support/MineContext/Data`
- **Windows**：`%APPDATA%\MineContext\Data`

## 本地 Embedding（Ollama）

此版本使用 **Ollama** 在本地运行 embedding 模型。你的上下文数据在 embedding 生成过程中永远不会离开你的机器——无需调用第三方 embedding 服务 API。

# 🏁 快速开始

## 1. 安装

从 [GitHub Releases](https://github.com/KJiShou/MineContext/releases) 下载，或从源码构建。

## 2. 配置 AI 模型

MineContext 需要两种类型的 AI 模型：

| 模型类型 | 用途 | 推荐 |
|---------|------|------|
| **VLM**（视觉语言模型） | 截图分析与理解 | MiniMax |
| **Embedding 模型** | 语义搜索与上下文检索 | Ollama bge-m3 |

### 推荐配置：MiniMax VLM + Ollama bge-m3

这个组合的优势：
- **MiniMax VLM**：低成本且一流的视觉理解能力
- **Ollama bge-m3**：最先进的 embedding 模型，100% 本地运行

### 设置 Ollama（Embedding 模型）

**安装 Ollama：**

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows：从 https://ollama.com/download 下载
```

**启动 Ollama：**
```bash
ollama serve
```

**下载 bge-m3 模型：**
```bash
ollama pull bge-m3
```

**验证安装：**
```bash
curl http://localhost:11434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "bge-m3", "input": "hello world"}'
```

### 在应用中配置

1. 启动 MineContext
2. 进入**设置（Settings）**
3. 选择 **MiniMax** 作为模型平台
4. 输入你的 MiniMax API key（从 [platform.minimaxi.com](https://platform.minimaxi.com/user-center/basic-information/interface-key) 获取）
5. 选择 VLM 模型（如 **MiniMax-M2.7**）
6. **启用"使用自定义 embedding 模型"**
7. 填写 embedding 详情：
   - **模型名称**：`bge-m3`
   - **Base URL**：`http://localhost:11434/v1`
   - **API Key**：任意字符串（Ollama 不需要认证——使用 `ollama`）
8. 点击**保存**

## 3. 开始录制

1. 进入**屏幕监控（Screen Monitor）**
2. 启用屏幕共享权限
3. 在**设置**中设置屏幕捕获区域
4. 点击**开始录制**

## 4. 忘掉它

MineContext 在后台工作。你的上下文会逐渐被收集。专注于你的工作——MineContext 会在后台为你生成待办、洞察和摘要。

# 🔧 后台调试

访问 `http://localhost:1733` 的调试控制台：

- 查看 Token 消耗
- 配置自动任务间隔
- 调整系统提示词

# 📐 系统架构

MineContext 采用模块化架构：

```
opencontext/
├── context_capture/    # 屏幕监控、文档监控
├── context_processing/ # 分块、实体提取、合并
├── context_consumption/# 内容生成
├── storage/            # SQLite + ChromaDB
├── llm/               # LLM 集成（OpenAI 兼容）
└── server/            # FastAPI REST API + WebSocket

frontend/
├── src/main/          # Electron 主进程
├── src/preload/       # 安全 IPC 桥接
└── src/renderer/     # React UI
```

## 从源码运行

```bash
# 构建后端
uv sync
./build.sh

# 安装前端依赖
cd frontend
pnpm install

# 开发模式
pnpm dev

# 打包
pnpm build:mac   # macOS
```

# 📃 许可证

Apache 2.0 - 参见 [LICENSE](LICENSE)

---

**Star History**

[![Star History Chart](https://api.star-history.com/svg?repos=KJiShou/MineContext&type=Timeline)](https://www.star-history.com/#KJiShou/MineContext&Timeline)
