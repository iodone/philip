# AGENTS.md — Philip 项目开发协议

> **结构先于实现，美即低熵。**
>
> 这是 Philip 项目的工作协议。所有开发工作应遵循本协议定义的流程和规范。

---

## 1. 项目概述

**Philip** 是 Bub 的主入口项目，负责启动、沙箱和 plugin 组装。

- **仓库**: https://github.com/iodone/philip
- **语言**: Python 3.12+
- **包管理**: uv
- **构建工具**: hatchling

---

## 2. 开发流程

### 2.1 分支命名规范

| Type | 场景 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/add-startup-guard` |
| `fix/` | Bug 修复 | `fix/sandbox-path-resolution` |
| `docs/` | 文档变更 | `docs/update-agents` |
| `refactor/` | 重构 | `refactor/simplify-run-host` |
| `chore/` | 构建/工具变更 | `chore/update-dev-tooling` |
| `style/` | 代码风格 | `style/fix-formatting` |

### 2.2 Commit Message 格式

```text
<type>(<scope>): <subject>

[optional body]
```

**示例**:

```text
fix(runtime): guard against duplicate gateway startup

- Add explicit duplicate-process check before launching gateway
- Clarify expected host-mode workspace semantics
```

---

## 3. 开发命令

### 3.1 基础命令

```bash
# 安装依赖
uv sync
uv sync --group dev

# 格式化代码
uv run black .

# 运行 lint 检查
uv run ruff check .
uv run mypy philip

# 运行测试
uv run pytest

# 构建包
uv build
```

说明：

- `uv sync` 默认只安装运行时依赖，适用于正式运行和发布环境
- `uv sync --group dev` 额外安装开发工具，仅用于本地开发、检查和测试

### 3.2 完整开发流程

```bash
# 1. 同步最新代码
git checkout main && git pull

# 2. 创建功能分支
git checkout -b feat/my-feature

# 3. 开发 & 测试
# ... 编辑代码 ...

# 4. 格式化 & 检查
uv sync --group dev
uv run black .
uv run ruff check .
uv run mypy philip
uv run pytest

# 5. 提交
git add <files>
git commit -m "feat(scope): description"

# 6. 推送分支
git push -u origin feat/my-feature
```

---

## 4. 代码规范

### 4.1 风格指南

- **行长度**: 88 字符（Black 默认）
- **格式化工具**: Black
- **Lint 工具**: Ruff（规则: E, F, I, UP）
- **类型检查**: mypy（strict 模式）

### 4.2 字符串折行规则

Black/Ruff format **不会自动折行字符串**。以下情况需手动拆分：

- 长 shell 命令
- 长 f-string
- 长说明文案和 docstring

---

## 5. 测试规范

### 5.1 测试文件命名

```text
tests/
├── test_run_host.py
├── test_entrypoint.py
└── ...
```

### 5.2 测试覆盖率

```bash
uv run pytest --cov=philip --cov-report=term-missing --cov-report=xml
```

---

## 6. 发布流程

### 6.1 版本更新

```bash
# 1. 更新版本号
# 编辑 pyproject.toml: [project].version

# 2. 提交版本变更
git add pyproject.toml uv.lock
git commit -m "chore(release): bump version to x.y.z"
```

### 6.2 发布 Tag

```bash
# 1. 同步主分支
git checkout main && git pull

# 2. 创建版本 tag
git tag vx.y.z
git push origin vx.y.z
```

---

## 7. CI / 校验流程

### 7.1 本地最小门槛

```text
format -> lint -> type-check -> test -> build
```

### 7.2 执行顺序

| 阶段 | 命令 | 说明 |
|------|------|------|
| format | `uv run black .` | 统一格式 |
| lint | `uv run ruff check .` | 静态检查 |
| type-check | `uv run mypy philip` | 严格类型检查 |
| test | `uv run pytest` | 回归验证 |
| build | `uv build` | 验证可构建 |

---

## 8. 版本管理

### 8.1 版本号规范

遵循 Semantic Versioning：

```text
MAJOR.MINOR.PATCH[-prerelease][+build]
```

### 8.2 版本来源

版本号定义在 `pyproject.toml` 的 `[project].version`。

---

## 9. 依赖管理

### 9.1 运行时依赖

运行时依赖统一声明在 `pyproject.toml` 的 `[project].dependencies` 中，例如：

```toml
dependencies = [
    "bub == 0.3.6",
    "bub-im-bridge @ git+https://github.com/iodone/bub-im-bridge.git",
]
```

### 9.2 开发依赖

开发工具统一放在 `pyproject.toml` 的 `[dependency-groups].dev` 中。

正式发布版本默认不会安装 `dev` 依赖；只有显式执行 `uv sync --group dev` 时才会安装开发工具。

---

## 10. 文档规范

### 10.1 文件结构

```text
philip/
├── README.md
├── AGENTS.md
├── docs/
├── pyproject.toml
└── uv.lock
```

### 10.2 文档要求

- README 负责项目定位、安装和运行方式
- AGENTS.md 负责开发流程和工程规范
- `docs/` 负责补充部署或专题说明
