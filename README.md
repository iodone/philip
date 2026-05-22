# Philip

Philip 是 [Bub](https://github.com/bubbuild/bub) 生态的主入口项目，提供两部分能力：

1. **Bub Distribution** — 多渠道 AI Agent 网关，支持飞书、Telegram、微信，通过 [boxsh](https://github.com/xicilion/boxsh) 沙箱隔离执行。负责启动、沙箱管理和 plugin 组装。
2. **CLI Capabilities** — 命令行工具集，管理 Bub workspace。当前重点是 `wiki`：workspace 初始化、知识库搜索、图分析、同步。Wiki 是 Bub workspace 的知识层，配合 agent 启动前的环境准备使用。

<!-- TODO: 加一张飞书对话截图或终端运行截图 -->

## 项目结构

```
philip/
├── src/
│   └── philip/                  # Python 包
│       ├── capabilities/       # CLI 能力模块
│       │   └── wiki/           # 知识库管理
│       ├── cli/                # CLI 入口（click）
│       ├── plugins/            # Bub 插件
│       └── skills/             # 内置 agent skill
├── tests/                      # 单元测试
├── docs/                       # 详细文档
│   ├── DOCKER_USAGE.md         # Docker 部署指南
│   └── WIKI.md                 # Wiki CLI 详细用法
├── run-host.sh                 # 宿主机模式启动脚本
├── entrypoint.sh               # Docker 容器入口
├── docker-compose.yml          # Docker 模式编排
├── Dockerfile                  # 容器镜像定义
├── .env.example                # 配置模板
├── pyproject.toml              # Python 依赖（含推荐插件）
└── AGENTS.md                   # Agent 运行规则
```

## 安装

### CLI 工具（推荐）

使用 `pipx` 安装 `philip` CLI，命令会注册到系统 PATH，agent 和 bash 脚本可直接调用：

```bash
pipx install git+https://github.com/iodone/philip.git
```

安装后即可在任意目录使用：

```bash
philip wiki init /path/to/workspace
philip wiki search "agent architecture"
philip wiki sync
```

### Bub 网关 / 从源码开发

Bub distribution 需要从源码运行（gateway 依赖不在 PyPI）：

```bash
git clone https://github.com/iodone/philip.git
cd philip
uv sync --extra gateway
```

## 快速开始

### 1. 初始化 Wiki Workspace

使用 `philip wiki init` 初始化一个 workspace。创建完整目录结构、模板文件，并自动将内置 skill 安装到 `.agents/skills/`：

```bash
philip wiki init /path/to/workspace
```

初始化后的 workspace 结构：

```
/path/to/workspace/
├── AGENTS.md               # Agent session 入口协议
├── README.md               # Workspace 总览
├── rules/
│   ├── SOUL.md             # Agent 身份定义
│   ├── USER.md             # 用户偏好与原则
│   ├── COMMUNICATION.md    # 协作方式
│   ├── SECURITY.md         # 安全规则
│   ├── WORKSPACE.md        # 目录路由速查
│   ├── axioms/             # 稳定判断规则
│   └── skills/             # Skill 索引
├── .agents/skills/
│   └── workflow-llm-wiki/SKILL.md  # 内置 wiki 操作 skill
├── contexts/               # 输入层（ingest 材料）
│   ├── blog/               # 博客草稿
│   ├── clippings/          # 外部原始资料
│   ├── daily_records/      # 日级记录
│   ├── life_record/        # 生活观察
│   ├── survey_sessions/    # 调研过程
│   └── thought_review/     # 深度分析
├── wiki/
│   ├── pages/              # Wiki 页面（Obsidian 兼容）
│   ├── wiki-purpose.md     # Wiki 目的与范围
│   ├── wiki-schema.md      # 页面规范
│   ├── wiki-agent.md       # Agent 行为规则
│   └── wiki-log.md         # 操作日志
└── .llm-wiki/
    └── config.toml         # Vault 配置
```

### 2. 配置并启动 Bub 网关

Bub distribution 部分需要从源码运行：

```bash
cp .env.example .env
# 编辑 .env，填入 BUB_MODEL、BUB_API_KEY、BUB_WORKSPACE（指向上面的 workspace）

# 宿主机开发模式（无 sandbox）
uv run bub -w /path/to/workspace gateway

# 宿主机隔离模式（boxsh sandbox）
./run-host.sh

# 或容器部署模式
docker-compose up -d
```

启动后，agent 会自动读取 workspace 中的 wiki skill，通过 `philip wiki search/graph/sync` 等命令管理知识库。

## CLI Capabilities

### Wiki

| 命令 | 说明 |
|:---|:---|
| `philip wiki init <dir>` | 初始化 workspace（目录结构 + 模板 + skill） |
| `philip wiki search <query>` | BM25 搜索（配置 DB9 后自动启用向量 + RRF 融合） |
| `philip wiki sync` | 变更检测（mtime + SHA-256），可选推送到 DB9 |
| `philip wiki graph` | 链接图分析：社区发现、hub 页、orphan 页、wanted 页 |
| `philip wiki status` | wiki 健康概览 |
| `philip wiki skill` | 管理 AI agent skill |

详细用法见 [docs/WIKI.md](docs/WIKI.md)。

## 配置

### 通用配置

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_MODEL` | LLM 模型，格式 `provider:model_id` | ✅ |
| `BUB_API_KEY` | API 密钥 | ✅ |
| `BUB_API_BASE` | API 端点（自定义模型时使用） | ❌ |
| `BUB_WORKSPACE` | Agent 工作空间路径 | ✅ |

### 飞书

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_FEISHU_APP_ID` | 应用 App ID | ✅ |
| `BUB_FEISHU_APP_SECRET` | 应用 App Secret | ✅ |
| `BUB_FEISHU_VERIFICATION_TOKEN` | Webhook 验证 Token | ❌ |
| `BUB_FEISHU_ENCRYPT_KEY` | Webhook 事件加密密钥 | ❌ |
| `BUB_FEISHU_ALLOW_USERS` | 允许的用户 open_id，逗号分隔 | ❌ |
| `BUB_FEISHU_ALLOW_CHATS` | 允许的 Chat ID，逗号分隔 | ❌ |
| `BUB_FEISHU_BOT_OPEN_ID` | 机器人 open_id，用于群聊 @检测 | ❌ |
| `BUB_FEISHU_BOT_NAME` | 机器人显示名称，用于 @名称 匹配 | ❌ |

### Telegram

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_TELEGRAM_TOKEN` | Bot Token（@BotFather 获取） | ✅ |
| `BUB_TELEGRAM_ALLOW_USERS` | 允许的用户 ID，逗号分隔 | ❌ |
| `BUB_TELEGRAM_ALLOW_CHATS` | 允许的 Chat ID，逗号分隔 | ❌ |

### 微信

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `WEIXIN_BASE_URL` | 微信 API 基础地址 | ❌ |
| `WEIXIN_ACCOUNT_ID` | 微信账号 ID | ❌ |

## 文档

- [Docker 部署指南](docs/DOCKER_USAGE.md) — 容器模式部署、调试、COW 沙箱
- [CLI Capabilities — Wiki](docs/WIKI.md) — wiki 命令详细用法、DB9 配置、workspace 结构

## License

MIT
