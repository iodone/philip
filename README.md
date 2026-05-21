# Philip

Philip 是 [Bub](https://github.com/bubbuild/bub) 生态的主入口项目，提供两部分能力：

1. **Bub Distribution** — 多渠道 AI Agent 网关（飞书、Telegram、微信），通过 [boxsh](https://github.com/xicilion/boxsh) 沙箱隔离执行，负责启动、沙箱管理和 plugin 组装。
2. **CLI Capabilities** — 独立于 Bub 运行时的命令行工具集。当前重点是 `wiki`：workspace 初始化、知识库搜索、图分析、同步。

两部分共享同一个项目，可以独立使用：Bub distribution 需要渠道配置和 LLM API；CLI capabilities 只需要 Python 环境。

## 快速上手

```bash
git clone https://github.com/iodone/philip.git
cd philip && uv sync
```

### 准备 Workspace

```bash
philip wiki init /path/to/workspace
```

创建完整目录结构（`wiki/`、`contexts/`、`rules/` 等），安装内置 skill，生成模板。重复运行安全。

### 启动 Gateway

```bash
# 宿主机模式
./run-host.sh

# Docker 模式
docker-compose up -d
```

需要在 `.env` 中配置 `BUB_MODEL`、`BUB_API_KEY`、`BUB_WORKSPACE`。详见 [.env.example](.env.example)。

## CLI Capabilities

| 命令 | 说明 |
|:---|:---|
| `philip wiki init <dir>` | 初始化 workspace |
| `philip wiki search <query>` | BM25 搜索（配置 DB9 后自动启用向量 + RRF） |
| `philip wiki sync` | 变更检测，可选推送到 DB9 |
| `philip wiki graph` | 链接图分析 |
| `philip wiki status` | wiki 健康概览 |

## 文档

- [Docker 部署指南](docs/DOCKER_USAGE.md)
- [CLI Capabilities — Wiki](docs/WIKI.md)

## License

MIT
