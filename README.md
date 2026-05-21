# Philip

Philip 是 [Bub](https://github.com/bubbuild/bub) 生态的主入口项目，负责 agent 启动、沙箱管理和 plugin 组装。支持飞书、Telegram、微信，通过 [boxsh](https://github.com/xicilion/boxsh) 沙箱隔离执行。

Philip 同时提供 CLI 能力管理 Bub workspace——当前重点是 `wiki`：workspace 初始化、知识库搜索、图分析、同步。Wiki 不是独立工具，它是 Bub workspace 的知识层。

## 快速上手

```bash
git clone https://github.com/iodone/philip.git
cd philip && uv sync

# 1. 初始化 workspace（创建目录结构、模板、skill）
uv run philip wiki init /path/to/workspace

# 2. 配置 .env（BUB_MODEL、BUB_API_KEY、BUB_WORKSPACE）
cp .env.example .env && vim .env

# 3. 启动
uv run bub -w /path/to/workspace gateway
```

`philip wiki init` 创建 workspace 全套结构：`wiki/`（知识库）、`contexts/`（输入层）、`rules/`（agent 规则）、`AGENTS.md` 等，自动安装内置 skill。重复运行安全。

Gateway 启动后，agent 读取 workspace 中的 wiki skill，通过 `philip wiki search/sync/graph` 管理知识库。

## CLI Capabilities

| 命令 | 说明 |
|:---|:---|
| `philip wiki init <dir>` | 初始化 workspace |
| `philip wiki search <query>` | BM25 搜索（配置 DB9 后自动启用向量 + RRF） |
| `philip wiki sync` | 变更检测，可选推送到 DB9 |
| `philip wiki graph` | 链接图分析 |
| `philip wiki status` | wiki 健康概览 |

## 文档

- [CLI Capabilities — Wiki](docs/WIKI.md) — wiki 命令详细用法、DB9 配置
- [Docker 部署指南](docs/DOCKER_USAGE.md) — 容器模式运行

## License

MIT
