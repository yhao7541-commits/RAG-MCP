# Modular RAG MCP Server

个人实现的模块化 RAG（Retrieval-Augmented Generation）服务框架。项目把文档摄取、混合检索、可选重排、响应组装、链路追踪和 MCP（Model Context Protocol）工具接口放在同一个本地工程中，方便把私有文档库接入支持 MCP 的 AI 客户端。

这个仓库更偏向工程骨架和本地可运行原型：核心模块都通过抽象接口和工厂方法组织，便于替换 LLM、Embedding、Reranker、Vector Store 和 Evaluator。

## 30 秒速览

| 面试官关心的问题 | 简短回答 |
| --- | --- |
| 项目解决什么问题 | 让 AI 助手能够检索本地/私有文档后再回答，减少模型凭记忆编答案的问题。 |
| 目标用户是谁 | 需要把私有文档、技术资料、PDF 知识库接入 Copilot、Claude、Cursor 等 AI 客户端的开发者或 RAG 学习者。 |
| 核心流程是什么 | PDF 摄取 → 文档切块 → Chunk 增强 → Dense/BM25 建索引 → Hybrid Search → RRF 融合 → 可选 Rerank → MCP/CLI/Dashboard 返回结果。 |
| 如何启动或看演示 | 先 `python scripts/ingest.py ...` 摄取文档，再用 `python scripts/query.py ... --verbose` 看检索链路，或 `python scripts/start_dashboard.py` 打开 Dashboard。 |
| 如何评测 | 使用 `python scripts/evaluate.py` 跑 golden test set；也可以执行 `pytest`、`pytest tests/unit`、`pytest -m "not llm"` 验证工程质量。 |
| 已知限制是什么 | 当前以本地原型为主，默认偏 PDF，本地 Chroma/BM25，生产级鉴权、多租户、远程部署、复杂表格/OCR 还需要继续扩展。 |

## 最快演示路径

```bash
# 1. 安装依赖后，摄取一个 PDF
python scripts/ingest.py --path tests/fixtures/sample_documents/simple.pdf --collection demo --force

# 2. 查看 Dense / Sparse / Fusion / Rerank 中间结果
python scripts/query.py --query "RAG 是什么" --collection demo --verbose

# 3. 打开本地 Dashboard
python scripts/start_dashboard.py

# 4. 运行评估或测试
python scripts/evaluate.py
pytest -m "not llm"
```

## Features

- PDF 文档摄取：支持单文件或目录递归摄取，默认处理 PDF。
- 多阶段 Ingestion Pipeline：文档加载、切分、Chunk Refinement、Metadata Enrichment、Embedding、向量写入。
- 混合检索：Dense Retrieval + BM25 Sparse Retrieval + RRF Fusion。
- 可选重排：支持关闭重排，也可按配置接入 Cross-Encoder 或 LLM Reranker。
- MCP 工具接口：通过 stdio transport 暴露知识库查询、集合列表、文档摘要等工具。
- Streamlit Dashboard：提供数据浏览、摄取管理、链路追踪、查询追踪和评估面板。
- 可观测性：Ingestion 和 Query 都会记录 trace，便于定位链路中的输入、输出和耗时。
- 测试分层：包含 unit、integration、e2e 测试目录，覆盖核心组件和主要链路。

## Architecture

```text
documents
  -> loader
  -> splitter
  -> chunk transforms
  -> embedding
  -> vector store / bm25 index
  -> hybrid search
  -> optional rerank
  -> response builder
  -> CLI / Dashboard / MCP tools
```

主要模块：

| Path | Responsibility |
| --- | --- |
| `src/ingestion/` | 文档摄取、切分、转换、向量写入和 BM25 索引 |
| `src/core/query_engine/` | Query 解析、Dense/Sparse 检索、RRF 融合、重排 |
| `src/core/response/` | 检索结果格式化、引用信息和多模态响应组装 |
| `src/libs/` | LLM、Embedding、Reranker、Loader、Splitter、Vector Store 的可插拔实现 |
| `src/mcp_server/` | MCP server、协议处理和工具注册 |
| `src/observability/` | 日志、trace、Dashboard 和评估流程 |
| `scripts/` | 本地摄取、查询、评估和 Dashboard 启动脚本 |
| `tests/` | 单元测试、集成测试、端到端测试和测试数据 |

## Requirements

- Python 3.10+
- Windows、macOS 或 Linux
- 一个可用的 Embedding provider
- 如需生成回答、Chunk Refinement、Metadata Enrichment 或 LLM Rerank，需要配置可用的 LLM provider

项目默认使用 ChromaDB 作为本地向量库，数据会写入 `data/`。该目录已被 `.gitignore` 排除。

## Installation

```bash
git clone https://github.com/yhao7541-commits/RAG-MCP.git
cd RAG-MCP

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
```

## Configuration

默认配置文件位于 `config/settings.yaml`。首次运行前至少需要确认以下部分：

```yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "YOUR_API_KEY_HERE"

embedding:
  provider: "openai"
  model: "text-embedding-ada-002"
  api_key: "YOUR_API_KEY_HERE"

vector_store:
  provider: "chroma"
  persist_directory: "./data/db/chroma"
  collection_name: "knowledge_hub"
```

支持的主要 provider：

| Component | Providers |
| --- | --- |
| LLM | `openai`, `azure`, `ollama`, `deepseek` |
| Vision LLM | `openai`, `azure`, `ollama` |
| Embedding | `openai`, `azure`, `ollama` |
| Vector Store | `chroma` |
| Reranker | `none`, `cross_encoder`, `llm` |
| Evaluator | `custom`, `ragas` |

不要把真实 API Key 提交到仓库。可以把本地密钥放在环境变量中，或只保存在未提交的个人配置文件里。

## Usage

### Ingest Documents

摄取单个 PDF：

```bash
python scripts/ingest.py --path documents/report.pdf --collection personal_docs
```

摄取目录中的 PDF：

```bash
python scripts/ingest.py --path documents/ --collection personal_docs
```

查看将要处理的文件但不写入数据：

```bash
python scripts/ingest.py --path documents/ --collection personal_docs --dry-run
```

强制重新处理：

```bash
python scripts/ingest.py --path documents/report.pdf --collection personal_docs --force
```

### Query From CLI

```bash
python scripts/query.py --query "RRF 是什么" --collection personal_docs
```

显示 Dense、Sparse、Fusion、Rerank 等中间结果：

```bash
python scripts/query.py --query "Azure OpenAI 配置步骤" --collection personal_docs --verbose
```

临时关闭重排：

```bash
python scripts/query.py --query "RRF 是什么" --collection personal_docs --no-rerank
```

### Start Dashboard

```bash
python scripts/start_dashboard.py
```

指定端口：

```bash
python scripts/start_dashboard.py --port 8502
```

默认地址为 `http://localhost:8501`。

## MCP Server

MCP server 使用 stdio transport。推荐从 MCP client 配置中调用：

```json
{
  "mcpServers": {
    "modular-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "D:\\Dev\\RAG\\MODULAR-RAG-MCP-SERVER"
    }
  }
}
```

暴露的工具：

| Tool | Purpose |
| --- | --- |
| `query_knowledge_hub` | 对知识库执行混合检索，返回带引用的结果 |
| `list_collections` | 列出本地向量库中的 collections，可附带统计信息 |
| `get_document_summary` | 按 `doc_id` 获取文档标题、摘要、来源和 chunk 数量 |

示例调用参数：

```json
{
  "query": "这份文档里如何配置 Azure OpenAI?",
  "top_k": 5,
  "collection": "personal_docs"
}
```

MCP stdio 对 stdout 很敏感，server 日志会被重定向到 stderr，避免污染 JSON-RPC 消息流。

## Dashboard

Dashboard 基于 Streamlit，面向本地调试和管理：

- Overview：查看系统状态和关键配置。
- Data Browser：浏览 collections、文档和 chunks。
- Ingestion Manager：从页面触发文档摄取。
- Ingestion Traces：查看摄取链路的阶段输出和耗时。
- Query Traces：查看查询链路的检索、融合、重排结果。
- Evaluation Panel：运行或查看评估结果。

Dashboard 和 CLI 使用同一套本地配置与数据目录。

## Evaluation

评测分两层：

- 检索质量：`scripts/evaluate.py` 读取 golden test set，关注 Hit Rate、MRR 等指标，用来判断 Top-K 是否找到了正确 chunk，以及正确 chunk 是否排得靠前。
- 工程回归：`pytest` 覆盖 unit、integration、e2e，验证配置加载、切块、检索、MCP 工具、Dashboard 服务和评估流程是否还能正常工作。

常用命令：

```bash
python scripts/evaluate.py
pytest
pytest -m "not llm"
```

## Testing

运行全部测试：

```bash
pytest
```

只运行单元测试：

```bash
pytest tests/unit
```

跳过需要外部服务的测试：

```bash
pytest -m "not llm"
```

代码风格检查：

```bash
ruff check .
```

## Project Structure

```text
.
├── config/
│   ├── prompts/
│   └── settings.yaml
├── scripts/
│   ├── ingest.py
│   ├── query.py
│   ├── evaluate.py
│   └── start_dashboard.py
├── src/
│   ├── core/
│   ├── ingestion/
│   ├── libs/
│   ├── mcp_server/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── main.py
├── pyproject.toml
└── README.md
```

## Implementation Notes

- `settings.yaml` 是主要配置入口，尽量通过配置切换 provider。
- `src/libs/*/base_*.py` 定义了各类 provider 的抽象接口。
- `src/libs/*/*_factory.py` 负责根据配置创建具体实现。
- Ingestion 写入 ChromaDB 和 BM25 两套索引，Query 阶段再做融合。
- Trace 文件默认写入 `logs/traces.jsonl`，该目录不进入 Git。
- `data/`、`logs/`、部分本地辅助目录、`.github/`、`DEV_SPEC.md` 均不纳入当前仓库提交范围。

## Known Limitations

- 当前项目定位是本地可运行原型和学习型工程骨架，不是开箱即用的生产 SaaS。
- 默认文档摄取重点是 PDF；Word、HTML、Markdown、Excel、复杂表格和扫描件 OCR 需要继续扩展。
- 默认使用本地 ChromaDB 和 BM25 索引；远程向量库、多租户隔离、鉴权和并发部署还未作为完整生产方案实现。
- Rerank、Vision Caption、Ragas 等能力依赖外部模型或可选依赖，未配置时应关闭或使用 fallback。
- 评估效果依赖 golden test set 质量；样例数据只能验证链路，不能代表真实业务效果。

## Roadmap

- 增加更多文档 loader，例如 Markdown、HTML、Word。
- 补充远程向量库实现，例如 Qdrant 或 Pinecone。
- 完善 Cross-Encoder Reranker 的本地模型下载与缓存流程。
- 增加 Dockerfile 和更完整的部署样例。
- 为 MCP client 配置补充更多平台示例。
- 扩展评估数据集和自动化回归报告。

## License

MIT
