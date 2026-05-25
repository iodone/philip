# JSON-RPC Channel

Philip 提供 JSON-RPC 2.0 通道，作为 Bub gateway 的一个 Channel 插件。支持 HTTP 和 WebSocket 两种传输方式，用于本地调试、CLI 交互和外部系统集成。

这条链路的边界先定死：

- **服务启动入口**：`uv run bub gateway`
- **Philip 的角色**：通过 plugin `provide_channels(...)` 向 Bub 注入 `JsonRpcChannel`
- **本地客户端入口**：`philip rpc chat`
- **会话键**：`session_id`
- **请求相关键**：JSON-RPC 顶层 `id`

## 启动

JSON-RPC 通道通过 Bub gateway 自动加载，无需单独启动：

```bash
# 开发模式
uv run bub -w /path/to/workspace gateway

# 宿主机模式
./run-host.sh
```

启动后默认监听 `127.0.0.1:8420`，暴露两个端点：

| 端点 | 传输 | 用途 |
|------|------|------|
| `POST /rpc` | HTTP | 单次请求/响应 |
| `GET /ws` | WebSocket | 持久连接，支持流式输出 |

如果你在源码仓库里联调，推荐直接运行：

```bash
uv run philip rpc chat
```

如果你已经用 `pipx` 安装了最新 `philip`，则可以直接运行：

```bash
philip rpc chat
```

## 通用请求格式

所有请求遵循 JSON-RPC 2.0 规范：

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "method": "chat.send",
  "params": {
    "session_id": "my-session",
    "message": "hello"
  }
}
```

- `id` — 请求标识，响应回原值
- `method` — 方法名（见下文）
- `params` — 参数对象

其中：

- `params.session_id`：跨多轮请求稳定存在，用来续同一个 Bub tape/chat
- 顶层 `id`：只用于 transport correlation，不能拿来代替 `session_id`

## 方法

### `chat.ping`

健康检查，无需 `session_id`。

**请求：**
```json
{"jsonrpc": "2.0", "id": "1", "method": "chat.ping", "params": {}}
```

**响应：**
```json
{"jsonrpc": "2.0", "result": {"pong": true}, "id": "1"}
```

### `session.get`

查询会话状态。

**请求：**
```json
{"jsonrpc": "2.0", "id": "2", "method": "session.get", "params": {"session_id": "s1"}}
```

**响应：**
```json
{"jsonrpc": "2.0", "result": {"session_id": "s1", "note": "..."}, "id": "2"}
```

### `chat.send`

发送消息，等待完整响应。支持 HTTP 和 WebSocket。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "chat.send",
  "params": {
    "session_id": "s1",
    "message": "hello"
  }
}
```

**响应：**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "session_id": "s1",
    "text": "你好！有什么可以帮你的？",
    "status": "completed"
  },
  "id": "3"
}
```

- `session_id` — 必需，字符串。同一 session_id 的请求共享会话上下文
- `message` — 用户消息内容
- 超时：300 秒
- 并发：同一 `session_id` 支持并发 unary 请求，响应按各自 JSON-RPC `id` 回传

### `chat.stream`

流式输出，**仅支持 WebSocket**。HTTP 请求会返回错误。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "chat.stream",
  "params": {
    "session_id": "s1",
    "message": "写一首诗"
  }
}
```

**流式事件（服务端推送）：**

每个事件是独立的 JSON-RPC 2.0 notification（无 `id` 字段）：

```json
{"jsonrpc": "2.0", "method": "chat.stream.event", "params": {"session_id": "s1", "event": "token", "delta": "春"}}
{"jsonrpc": "2.0", "method": "chat.stream.event", "params": {"session_id": "s1", "event": "token", "delta": "眠"}}
```

**事件类型：**

| event | 说明 | 额外字段 |
|-------|------|----------|
| `token` | 文本增量 | `delta` |
| `tool_call` | 工具调用 | `name`, `args` |
| `tool_result` | 工具返回 | `name`, `result` |
| `error` | 流式错误 | `message` |
| `done` | 流结束 | `text`（完整文本） |

**最终响应（JSON-RPC response）：**

流结束后发送标准 JSON-RPC 响应：

```json
{
  "jsonrpc": "2.0",
  "result": {"session_id": "s1", "text": "春眠不觉晓...", "status": "completed"},
  "id": "4"
}
```

**限制：** 同一 `session_id` 同时只能有一个活跃流。第二个并发 `chat.stream` 会被显式拒绝，返回错误码 `-32002`，避免覆盖前一个流。

## 错误码

| code | 含义 |
|------|------|
| `-32700` | 解析错误（无效 JSON） |
| `-32600` | 无效请求 |
| `-32601` | 方法不存在 |
| `-32602` | 无效参数 |
| `-32603` | 内部错误 / 超时 |
| `-32000` | 缺少 `session_id` |
| `-32001` | HTTP 不支持 `chat.stream` |
| `-32002` | 同一 session 已有活跃流 |

## CLI 客户端

Philip 提供交互式 REPL 客户端用于本地测试：

```bash
# HTTP 模式（默认）
philip rpc chat

# 源码仓库中联调时，推荐显式走当前 repo 环境
uv run philip rpc chat

# WebSocket 模式
philip rpc chat --ws

# WebSocket 流式模式
philip rpc chat --ws --stream

# 指定 session ID
philip rpc chat --session my-session

# 指定端点
philip rpc chat --url http://localhost:9000/rpc
```

**内置命令：**

| 命令 | 说明 |
|------|------|
| `/session` | 显示当前 session ID |
| `/help` | 帮助 |
| `/quit` | 退出（也可用 `/exit`、`/q`、Ctrl-D） |

典型验证顺序：

1. 启动 `uv run bub -w /path/to/workspace gateway`
2. 新开终端执行 `uv run philip rpc chat`
3. 用默认 HTTP 模式验证 `chat.send`
4. 执行 `uv run philip rpc chat --ws --stream --session demo`
5. 用固定 `session_id` 验证续聊与流式行为

## 使用 curl 测试

```bash
# ping
curl -s http://localhost:8420/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"chat.ping","params":{}}'

# 发送消息
curl -s http://localhost:8420/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"2","method":"chat.send","params":{"session_id":"test","message":"hello"}}'
```

## 架构

```
┌─────────────┐     POST /rpc      ┌──────────────────┐
│  HTTP 客户端  │ ──────────────────→ │                  │
└─────────────┘                     │  JsonRpcChannel   │
┌─────────────┐     GET /ws        │  (Bub Channel)    │
│  WS 客户端   │ ←────────────────→ │                  │
└─────────────┘                     └────────┬─────────┘
                                             │ on_receive
                                    ┌────────▼─────────┐
                                    │   Bub Framework   │
                                    │  (process_inbound)│
                                    └──────────────────┘
```

JsonRpcChannel 作为 Bub gateway 插件，通过 `provide_channels` hookimpl 注册。传输层只负责 JSON-RPC 协议解析和连接管理，业务逻辑由 Bub framework 处理。

## 当前支持说明

- 支持 HTTP unary：`chat.ping`、`session.get`、`chat.send`
- 支持 WebSocket unary：`chat.ping`、`session.get`、`chat.send`
- 支持 WebSocket streaming：`chat.stream`
- 不支持 HTTP streaming：HTTP 调 `chat.stream` 返回 `-32001`
- 不支持同一 `session_id` 的并发 active stream：返回 `-32002`
