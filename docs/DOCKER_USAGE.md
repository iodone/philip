# Docker 部署指南

## 快速开始

### 1. 准备配置

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

编辑 `.env` 文件，**必需**修改 `BUB_WORKSPACE` 为你的实际工作空间路径。

### 2. 创建必要目录

```bash
mkdir -p ~/.bub ~/.agents/skills ~/work/boxsh/philip
```

### 3. 微信渠道登录（可选）

如果使用微信渠道，需要先在本地登录：

```bash
uv run -m bub_im_bridge login
```

### 4. 启动容器

```bash
docker-compose up -d
```

### 5. 查看日志

```bash
docker-compose logs -f
```

## 目录挂载说明

| 容器内路径 | 环境变量 | 默认值 | 沙箱权限 | 说明 |
|-----------|---------|-------|---------|------|
| `/workspace-base` | `BUB_WORKSPACE` | (必需) | (基座) | COW 只读基座（Docker volume，不在沙箱内直接暴露） |
| `/workspace` | `BUB_BOXSH` | `~/work/boxsh/philip` | 🐄 COW | Agent 工作空间（boxsh COW merged view），写入持久化到宿主机 |
| `/root/.agents/skills` | `BUB_SKILLS` | `~/.agents/skills` | 🔒 只读 | Bub 技能目录 |
| `/root/.openclaw/openclaw-weixin` | `BUB_WEIXIN_DATA` | `~/.openclaw/openclaw-weixin` | ✏️ 可写 | 微信登录凭据 + 同步状态 |
| `/root/.bub` | `BUB_HOME` | `~/.bub` | ✏️ 可写 | Bub 运行数据（tapes、配置） |

## 沙箱保护

容器内使用 [boxsh](https://github.com/xicilion/boxsh) 沙箱运行 bub 服务，提供进程级别的文件系统隔离：

- ✅ Agent 可以读写 `/workspace`（COW merged view，基座来自 $BUB_WORKSPACE）
- ✅ Agent 可以在 `/root/.bub` 中写入 tapes 和配置
- ✅ Agent 对 `/workspace` 的写操作通过 COW 持久化到宿主机 `$BUB_BOXSH`，原始 workspace 不受影响
- ❌ Agent **无法**修改 skills 和 weixin 配置（防止意外覆盖）

即使 AI agent 生成了 `rm -rf /workspace` 这样的危险命令，也不会对宿主机的原始 workspace 造成影响。所有写入、删除、覆盖都沉淀到宿主机 `$BUB_BOXSH` 目录。

## 调试和运维

### 进入容器调试

entrypoint 通过 `exec boxsh --sandbox ...` 启动服务，boxsh 使用 `cow:/workspace-base:/workspace` 建立 COW overlay 并创建独立的 mount namespace（沙箱视图）。

```bash
# 1. 启动与 bub 同配置的新 boxsh 调试实例（推荐）
#    /workspace 可读写（独立的 COW merged view），skills 只读
#    适合验证 agent 在沙箱中的行为、测试文件读写
docker-compose run --rm bub /entrypoint.sh shell

# 2. 查看当前运行态（继承服务的沙箱视图）
#    可查看进程、环境变量、/root/.bub 等，但 /workspace 受 fuse 限制不可访问
docker-compose exec bub /entrypoint.sh shell

# 3. 进入原始镜像环境（绕过 boxsh，启动新容器）
#    适合排查镜像内容、确认文件是否被正确打包
docker-compose run --rm --entrypoint sh bub
```

在沙箱内，你可以验证 COW 和只读保护：

```bash
# 测试 COW 写入（应该成功，但不修改原始 workspace）
echo "test" > /workspace/test.txt
cat /workspace/test.txt
# 输出：test（通过 COW 层读取）

# 在宿主机验证原始 workspace 未被修改
# ls $BUB_WORKSPACE/test.txt → 不存在

# 测试 skills 目录只读（应该失败）
touch /root/.agents/skills/test.txt
# 输出：Read-only file system

# 测试可写目录（应该成功）
touch /root/.bub/test.txt
echo "success" > /root/.bub/test.txt
```

### 执行单个命令

```bash
# 在沙箱内查看文件（通过 entrypoint）
docker-compose exec bub /entrypoint.sh ls -la /workspace

# 在沙箱内查看 bub 配置
docker-compose exec bub /entrypoint.sh cat /root/.bub/config.yaml
```

### 查看日志

```bash
# 查看实时日志
docker-compose logs -f bub

# 查看最近 100 行
docker-compose logs --tail 100 bub
```

### 重启容器

```bash
docker-compose restart bub
```

### 停止容器

```bash
docker-compose down
```

## 环境变量配置

在 `.env` 文件中配置：

### 必需配置

```bash
# Agent 工作空间路径（必需修改为实际路径）
BUB_WORKSPACE=/path/to/your/workspace

# LLM 模型配置
BUB_MODEL=anthropic:claude-sonnet-4-20250514
BUB_API_KEY=sk-ant-xxxxx
```

### 可选配置

```bash
# Bub 相关目录（使用默认值即可）
BUB_BOXSH=~/work/boxsh/philip
BUB_SKILLS=~/.agents/skills
BUB_WEIXIN_DATA=~/.openclaw/openclaw-weixin
BUB_HOME=~/.bub

# 渠道配置（根据需要启用）
# 飞书
BUB_FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
BUB_FEISHU_APP_SECRET=your-app-secret

# Telegram
BUB_TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
BUB_TELEGRAM_PROXY=http://127.0.0.1:1087

# 其他配置...
```

完整配置参考项目根目录的 `.env.example` 文件。

## 架构说明

### 容器结构

```
宿主机
 ├── $BUB_WORKSPACE (原始工作区，不被修改)
 ├── $BUB_BOXSH (COW 写层，持久化 agent 写入)
 └── Docker 容器
      ├── /workspace-base ← $BUB_WORKSPACE (只读基座)
      ├── /workspace      ← $BUB_BOXSH (COW upper layer)
      └── boxsh 沙箱 (cow:/workspace-base:/workspace)
           ├── /workspace = COW merged view (agent workspace)
           └── bub gateway 进程 (bub -w /workspace)
```

### entrypoint.sh 用法

容器的入口点 `/entrypoint.sh` 支持多种使用方式：

```bash
# 1. 默认启动服务（无参数）
/entrypoint.sh
# → 在 boxsh 沙箱内启动 bub gateway

# 2. 进入交互式 shell（继承沙箱保护）
/entrypoint.sh shell
# → 在沙箱视图下启动交互式 shell

# 3. 执行单个命令（继承沙箱保护）
/entrypoint.sh <command>
# → 在沙箱视图下执行命令
```

## 常见问题

### Q: 为什么要使用 boxsh 沙箱？

A: boxsh 提供进程级别的文件系统隔离，防止 AI agent 执行的命令意外修改重要文件。即使 agent 生成了 `rm -rf /workspace` 这样的危险命令，也不会对宿主机的原始 workspace 造成影响。

### Q: 沙箱会影响性能吗？

A: 几乎没有影响。boxsh 使用 OS 原生的 overlay 机制（Linux 上是 overlayfs，macOS 上是 APFS clonefile），读取操作是零开销的，直接访问原始文件。

### Q: 如何临时禁用沙箱？

A: 修改 `entrypoint.sh`，去掉 `--sandbox` 和所有 `--bind` 参数，或者直接用 `docker exec -it bub bash` 进入非沙箱环境进行调试。

### Q: 沙箱内的进程能访问网络吗？

A: 可以。当前配置没有使用 `--new-net-ns` 参数。如需隔离网络，在 `entrypoint.sh` 的 `BOXSH_ARGS` 中添加 `--new-net-ns`。

### Q: 容器启动失败怎么办？

A: 检查以下几点：
1. `.env` 文件中的 `BUB_WORKSPACE` 路径是否正确
2. 挂载的目录是否存在
3. 查看容器日志：`docker logs bub`

### Q: 如何更新镜像？

A: 拉取最新代码后重新构建：

```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

### Q: 数据会丢失吗？

A: 不会。所有重要数据都通过 volume 挂载，存储在宿主机上：
- `/root/.bub` → `$BUB_HOME`（tapes、配置）
- `/root/.openclaw/openclaw-weixin` → `$BUB_WEIXIN_DATA`（微信凭据）
- `/workspace` → `$BUB_BOXSH`（agent 对 workspace 的 COW 写入）

容器删除重建后，这些数据仍然存在。
