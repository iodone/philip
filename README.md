# Philip

Philip 是 [Bub](https://github.com/bubbuild/bub) 生态的 Distribution，统一 gateway 启动、workspace 管理和 wiki 能力。

wiki 不是独立工具，它是 Bub workspace 的知识层：`philip wiki.init` 创建完整的 Bub workspace（rules / contexts / skills / wiki），`bub -w <workspace>` 在其上运行 agent，agent 通过 `philip wiki.*` 操作知识库。

## 快速开始

```bash
git clone https://github.com/iodone/philip.git
cd philip && uv sync

# 1. 初始化 workspace（目录结构、模板、内置 skill；可重复运行）
uv run philip wiki.init directory=/path/to/workspace

# 2. 配置 .env（必需：BUB_MODEL / BUB_API_KEY / BUB_WORKSPACE）
cp .env.example .env && vim .env

# 3. 启动 gateway
uv run philip gateway.start workspace=/path/to/workspace
```

需要全局 `philip` 命令时（agent 跑 bash、RPC 联调等场景），用 `uv tool install git+https://github.com/iodone/philip.git` 安装。

## CLI 命令

| 命令 | 说明 |
|:---|:---|
| `philip wiki.init directory=<dir>` | 初始化 workspace |
| `philip wiki.search query=<text>` | BM25 搜索（+ ripgrep 精确匹配，exact 优先） |
| `philip wiki.sync` | 变更检测（mtime + 内容哈希），更新同步状态 |
| `philip wiki.graph` | 链接图分析 |
| `philip wiki.status` | wiki 健康概览 |
| `philip gateway.start [workspace=<dir>] [enable_channel=<name>]` | 启动 message listeners |
| `philip rpc.chat [ws=true] [stream=true]` | 交互式 RPC REPL |

## 配置

| 配置项 | 说明 | 必需 |
|--------|------|:----:|
| `BUB_MODEL` | LLM 模型，格式 `provider:model_id` | ✅ |
| `BUB_API_KEY` | API 密钥 | ✅ |
| `BUB_WORKSPACE` | Agent 工作空间路径 | ✅ |
| `BUB_API_BASE` | API 端点（自定义模型时使用） | ❌ |

Channel（飞书 / Telegram / 微信）、部署路径、沙箱等完整配置见 [.env.example](.env.example)。

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

## 文档

- [Wiki CLI 详细用法](docs/WIKI.md) — wiki 命令详解、workspace 结构
- [JSON-RPC Channel API](docs/JSONRPC_CHANNEL.md) — gateway RPC 端点、宿主机模式（run-host.sh）
- [Docker 部署指南](docs/DOCKER_USAGE.md) — 容器部署与 boxsh 沙箱隔离

## License

MIT
