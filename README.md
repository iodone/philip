# Philip

Bub 主入口项目 — 启动、沙箱、plugin 组装。

通过 [boxsh](https://github.com/xicilion/boxsh) 沙箱运行 [Bub](https://github.com/bubbuild/bub) 框架，提供宿主机模式和 Docker 模式两种部署方式。

## 安装

```bash
git clone https://github.com/iodone/philip.git
cd philip
uv sync
```

## 快速开始

### 1. 准备配置

```bash
cp .env.example .env
```

编辑 `.env`，填入必要配置（至少需要 `BUB_MODEL`、`BUB_API_KEY`、`BUB_WORKSPACE`）。

### 2. 选择部署模式

#### 宿主机模式（推荐开发调试）

直接在宿主机用 boxsh 沙箱运行，无需 Docker。要求 boxsh >= 2.1.0。

```bash
./run-host.sh
```

> **注意：** `./run-host.sh shell` 交互模式因 boxsh 自身限制暂不支持，仅可使用 `./run-host.sh` 启动网关服务。

#### Docker 模式（推荐生产部署）

```bash
# 微信渠道需要先登录
uv run -m bub_im_bridge login

# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

📖 **详细 Docker 文档**：[docs/DOCKER_USAGE.md](docs/DOCKER_USAGE.md)

## Workspace 路径映射

| 角色 | Docker 模式 | 宿主机模式 |
|------|-------------|------------|
| 基座 workspace | `/workspace-base`（来自 `$BUB_WORKSPACE`） | `$BUB_WORKSPACE` |
| 写入层 | `/workspace`（来自 `$BUB_BOXSH`，COW upper） | `$BUB_WORKSPACE`（直接读写） |
| Runtime workspace | `/workspace` | `$BUB_WORKSPACE` |

> **重要：** Docker 模式使用 `BUB_BOXSH` 作为 COW upper；宿主机模式直接读写 `BUB_WORKSPACE`。App 代码通过 `bub -w` 参数动态获取路径，不硬编码任何路径。

## 沙箱保护

| 目录 | 权限 | 说明 |
|------|------|------|
| workspace | 宿主机模式可写 / Docker 模式 COW | Agent 工作空间 |
| project repo | 宿主机模式可写 | `run-host.sh` 所在仓库；`uv run` 需要写 repo-local `.venv` |
| skills | 只读 | Bub 技能目录 |
| weixin data | 可写 | 微信登录凭据 + 同步状态 |
| feishu auth | 可写 | feishu CLI 登录凭据（`~/.feishu`，token 刷新需要写权限） |
| bub home | 可写 | Bub 运行数据（tapes、配置） |

## 推荐插件

宿主机模式下，`run-host.sh` 每次执行前会自动预装以下插件：

- `bub-web-search@main` — Web 搜索能力
- `bub-schedule@main` — 定时任务

## 配置参考

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
| `BUB_WEIXIN_DATA` | 微信数据目录（沙箱内可写） | `~/.openclaw/openclaw-weixin` |
| `BUB_FEISHU_HOME` | Feishu CLI 认证目录（沙箱内可写） | `~/.feishu` |
| `BUB_HOME` | Bub 主目录（tapes、配置） | `~/.bub` |

### Agent 运行时

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BUB_MAX_STEPS` | Agent 最大执行步数 | 50 |
| `BUB_MAX_TOKENS` | 最大 token 数 | 16384 |
| `BUB_MODEL_TIMEOUT_SECONDS` | 模型调用超时（秒） | 300 |

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
| `BUB_FEISHU_BOT_NAME` | 机器人显示名称，用于 @名称 匹配（大小写不敏感） | ❌ |
| `BUB_FEISHU_QUEUE_MAX_LENGTH` | 消息队列最大长度，0=不限制 | 0 |
| `BUB_FEISHU_ADMIN_USERS` | 管理员 open_id，逗号分隔；管理员消息绕过排队，可发送 `,cancel` 取消任务 | ❌ |

> **获取机器人 open_id 的方式**：
>
> 方式一：启动服务后在群聊中 @机器人，查看日志输出的 `mentions.id.open_id`
>
> 方式二：通过 API 获取：
> ```bash
> curl -X GET "https://open.feishu.cn/open-apis/bot/v3/info/" \
>   -H "Authorization: Bearer <tenant_access_token>"
> ```

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

```bash
# 启动与 bub 同配置的 boxsh 调试实例
docker-compose run --rm bub /entrypoint.sh shell

# 查看当前运行态
docker-compose exec bub /entrypoint.sh shell

# 进入原始镜像环境（绕过 boxsh）
docker-compose run --rm --entrypoint sh bub
```

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
