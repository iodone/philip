# Philip

Philip 是一个基于 [Bub](https://github.com/bubbuild/bub) 框架的多渠道 AI Agent 网关，支持飞书、Telegram、微信，通过 [boxsh](https://github.com/xicilion/boxsh) 沙箱隔离执行。它负责启动、沙箱管理和 plugin 组装，是 Bub 生态的主入口项目。

<!-- TODO: 加一张飞书对话截图或终端运行截图 -->

## 项目结构

```
philip/
├── run-host.sh          # 宿主机模式启动脚本
├── entrypoint.sh        # Docker 容器入口
├── docker-compose.yml   # Docker 模式编排
├── Dockerfile           # 容器镜像定义
├── .env.example         # 配置模板
├── pyproject.toml       # Python 依赖（含推荐插件）
├── docs/
│   └── DOCKER_USAGE.md  # Docker 详细使用文档
└── AGENTS.md            # Agent 运行规则
```

## 安装

```bash
git clone https://github.com/iodone/philip.git
cd philip
uv sync
```

## 快速开始

```bash
cp .env.example .env
# 编辑 .env，填入 BUB_MODEL、BUB_API_KEY、BUB_WORKSPACE

# 宿主机模式（开发调试）
./run-host.sh

# 或 Docker 模式（生产部署）
docker-compose up -d
```

## 部署模式

| | 宿主机模式 | Docker 模式 |
|---|---|---|
| **适用场景** | 开发调试 | 生产部署 |
| **沙箱** | boxsh 直接运行 | boxsh in container |
| **workspace 写入** | 直接读写 `$BUB_WORKSPACE` | COW upper（`$BUB_BOXSH`） |
| **依赖** | boxsh >= 2.1.0 | Docker + Docker Compose |
| **启动** | `./run-host.sh` | `docker-compose up -d` |

## 沙箱权限

| 目录 | 权限 | 说明 |
|------|------|------|
| workspace | 宿主机模式可写 / Docker 模式 COW | Agent 工作空间 |
| project repo | 宿主机模式可写 | `run-host.sh` 所在仓库 |
| skills | 只读 | Bub 技能目录 |
| weixin data | 可写 | 微信登录凭据 + 同步状态 |
| feishu auth | 可写 | feishu CLI 登录凭据 |
| bub home | 可写 | Bub 运行数据（tapes、配置） |

## 配置

### 通用配置

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_MODEL` | LLM 模型，格式 `provider:model_id` | ✅ |
| `BUB_API_KEY` | API 密钥 | ✅ |
| `BUB_API_BASE` | API 端点（自定义模型时使用） | ❌ |
| `BUB_WORKSPACE` | Agent 工作空间路径 | ✅ |

### 部署路径

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BUB_BOXSH` | Docker 模式 COW upper 层 | `~/work/boxsh/philip` |
| `BUB_SKILLS` | Skills 目录（沙箱内只读） | `~/.agents/skills` |
| `BUB_WEIXIN_DATA` | 微信数据目录 | `~/.openclaw/openclaw-weixin` |
| `BUB_FEISHU_HOME` | Feishu CLI 认证目录 | `~/.feishu` |
| `BUB_HOME` | Bub 主目录（tapes、配置） | `~/.bub` |

### Agent 运行时

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BUB_MAX_STEPS` | Agent 最大执行步数 | 50 |
| `BUB_MAX_TOKENS` | 最大 token 数 | 16384 |
| `BUB_MODEL_TIMEOUT_SECONDS` | 模型调用超时（秒） | 300 |

### Vision tool（可选）

Philip 可为含图片的消息提供视觉分析能力。主模型在判断图片内容与问题相关时，调用 `vision.inspect_current_images` 工具，由单独配置的多模态模型读取图片并返回压缩文字观察结果。

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_VISION_MODEL` | 多模态模型，格式 `provider:model_id` | ✅ |
| `BUB_VISION_API_KEY` | 视觉模型 API 密钥 | ✅ |
| `BUB_VISION_API_BASE` | 视觉模型 API 端点 | ✅ |

> 不配置时，视觉工具不可用，不影响主模型的正常文字推理能力。

### Channel Manager

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BUB_ENABLED_CHANNELS` | 启用的渠道，逗号分隔或 `all` | `all` |
| `BUB_DEBOUNCE_SECONDS` | 消息防抖间隔（秒） | 1.0 |
| `BUB_MAX_WAIT_SECONDS` | 最大等待时间（秒） | 10.0 |
| `BUB_ACTIVE_TIME_WINDOW` | 活跃时间窗口（秒） | 60.0 |

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
| `BUB_FEISHU_QUEUE_MAX_LENGTH` | 消息队列最大长度，0=不限制 | 0 |
| `BUB_FEISHU_ADMIN_USERS` | 管理员 open_id，绕过排队 | ❌ |

> **获取机器人 open_id**：启动服务后在群聊中 @机器人，查看日志输出的 `mentions.id.open_id`；或通过 [Bot Info API](https://open.feishu.cn/open-apis/bot/v3/info/) 获取。

### Telegram

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_TELEGRAM_TOKEN` | Bot Token（@BotFather 获取） | ✅ |
| `BUB_TELEGRAM_ALLOW_USERS` | 允许的用户 ID，逗号分隔 | ❌ |
| `BUB_TELEGRAM_ALLOW_CHATS` | 允许的 Chat ID，逗号分隔 | ❌ |
| `BUB_TELEGRAM_PROXY` | HTTP 代理地址 | ❌ |

### 微信

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `WEIXIN_BASE_URL` | 微信 API 基础地址 | ❌ |
| `WEIXIN_ACCOUNT_ID` | 微信账号 ID | ❌ |

## Docker 调试

三种进入容器的方式，适用场景不同：

```bash
# 1. 启动与 bub 同配置的调试实例（boxsh 沙箱内）
docker-compose run --rm bub /entrypoint.sh shell

# 2. 进入正在运行的容器（boxsh 沙箱内）
docker-compose exec bub /entrypoint.sh shell

# 3. 进入原始镜像环境（绕过 boxsh，用于排查沙箱问题）
docker-compose run --rm --entrypoint sh bub
```

| 方式 | 环境 | 用途 |
|------|------|------|
| `run ... shell` | boxsh 沙箱 | 调试与运行态一致的环境 |
| `exec ... shell` | boxsh 沙箱 | 连接已运行容器，查看运行态 |
| `--entrypoint sh` | 原始镜像 | 排查沙箱本身的问题 |

📖 更多 Docker 用法见 [docs/DOCKER_USAGE.md](docs/DOCKER_USAGE.md)

## 常见问题

**宿主机模式 `.venv` 写入失败？**
- `uv run` 可能需要更新 repo-local `.venv`，确保项目目录可写

**Docker 模式启动失败？**
- 检查 `.env` 中 `BUB_WORKSPACE` 路径是否正确
- 检查挂载目录是否存在
- 查看日志：`docker-compose logs -f`

**微信登录失败？**
- 登录凭据存储在 `~/.openclaw/openclaw-weixin/`
- 重新执行 `uv run -m bub_im_bridge login`

## License

MIT
