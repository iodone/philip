# Philip

Philip 是 [Bub](https://github.com/bubbuild/bub) 生态的 Distribution ，统一了 gateway 启动、workspace 管理和 CLI 工具。

## 安装

从 GitHub 安装：

```bash
uv tool install git+https://github.com/iodone/philip.git
```

从本地源码安装：

```bash
git clone https://github.com/iodone/philip.git
cd philip
uv tool install . --force --reinstall
```

安装后 `philip` 命令全局可用。

## 快速开始

### 1. 初始化 Workspace

```bash
philip wiki.init directory=/path/to/workspace
```

创建完整目录结构、模板文件和内置 skill。详细结构见 [docs/WIKI.md](docs/WIKI.md)。

### 2. 配置并启动 Gateway

```bash
cp /path/to/philip/.env.example /path/to/workspace/.env
# 编辑 .env，填入 BUB_MODEL、BUB_API_KEY、BUB_WORKSPACE

# 启动所有 channel
philip gateway.start workspace=/path/to/workspace

# 只启动指定 channel
philip gateway.start workspace=/path/to/workspace enable_channel=feishu

# 宿主机沙箱模式（boxsh 隔离）
./run-host.sh
```

## CLI 命令

### Wiki

| 命令 | 说明 |
|:---|:---|
| `philip wiki.init directory=<dir>` | 初始化 workspace |
| `philip wiki.search query=<text>` | BM25 + 向量搜索 |
| `philip wiki.sync` | 变更检测，可选推送到 DB9 |
| `philip wiki.graph` | 链接图分析 |
| `philip wiki.status` | wiki 健康概览 |

### Gateway

| 命令 | 说明 |
|:---|:---|
| `philip gateway.start` | 启动所有 message listener |
| `philip gateway.start enable_channel=<name>` | 启动指定 channel |

### RPC Chat

| 命令 | 说明 |
|:---|:---|
| `philip rpc.chat` | 交互式 REPL（HTTP） |
| `philip rpc.chat ws=true` | WebSocket 模式 |
| `philip rpc.chat ws=true stream=true` | 流式输出 |

## 扩展

Philip 通过 entry-point 机制支持 CLI 扩展。扩展包将自定义 operation 注册到 `philip` 命令下。

### 创建扩展

```python
# my_pkg/echo.py
from rub.schema import Operation, OperationDetail
from rub.adapter import ExecutionResult

OPERATIONS = [Operation(operation_id="my.echo", display_name="Echo", description="Echo input")]
DETAILS = {"my.echo": OperationDetail(operation_id="my.echo", display_name="Echo", description="Echo input", parameters=[], invocation_examples=["philip my.echo message=hello"])}

def execute(args):
    return ExecutionResult(data={"echo": args.get("message", "")})

_EXECUTE = {"my.echo": (False, execute)}
```

```toml
# pyproject.toml
[project]
name = "my-tools"
dependencies = ["philip @ git+https://github.com/iodone/philip.git@main"]

[project.scripts]
philip = "philip.cli.__main__:app"

[project.entry-points.'philip.extensions']
my-tools = "my_pkg.echo"
```

```bash
uv tool install . --force
philip my.echo message=hello
```

### 扩展约定

- `OPERATIONS: list[Operation]` — operation 声明
- `DETAILS: dict[str, OperationDetail]` — 参数 schema
- `_EXECUTE: dict[str, tuple[bool, Callable]]` — `operation_id → (is_async, execute_fn)`
- operation ID 用 `扩展名.操作名` 格式避免冲突

## 配置

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_MODEL` | LLM 模型，格式 `provider:model_id` | ✅ |
| `BUB_API_KEY` | API 密钥 | ✅ |
| `BUB_WORKSPACE` | Agent 工作空间路径 | ✅ |
| `BUB_API_BASE` | API 端点（自定义模型时使用） | ❌ |

### 飞书

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_FEISHU_APP_ID` | 应用 App ID | ✅ |
| `BUB_FEISHU_APP_SECRET` | 应用 App Secret | ✅ |
| `BUB_FEISHU_BOT_OPEN_ID` | 机器人 open_id | ❌ |

### Telegram

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_TELEGRAM_TOKEN` | Bot Token | ✅ |

### 微信

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `WEIXIN_BASE_URL` | 微信 API 基础地址 | ❌ |

## 文档

- [Wiki CLI 详细用法](docs/WIKI.md)
- [JSON-RPC Channel API](docs/JSONRPC_CHANNEL.md)
- [Docker 部署指南](docs/DOCKER_USAGE.md)

## License

MIT
