---
name: workflow-gitlab
description: |
  GitLab MR 工作流程 skill，使用 glab CLI 管理完整的 Developer/Reviewer 流程。
  当用户提到以下场景时必须使用：创建分支、提交代码、创建 MR、review 代码、
  合并 MR、release、处理 review 反馈、git workflow、代码协作、PR 流程。
  即使用户只说"帮我提个 MR"或"review 一下这个分支"也要触发。
---

**HARD GATE：** 本 skill 只做 GitLab MR 工作流程管理。
不执行业务代码逻辑，不修改非 git 相关文件，不代替用户做最终决策。
所有 push、MR、merge、release 操作必须等待用户确认。

---

# GitLab Workflow Skill (glab)

基于 `glab` CLI 的 GitLab 协作工作流程，定义 **Developer** 和 **Reviewer** 两个角色。

## 核心原则

| 原则 | 实践 |
| :--- | :--- |
| **人类掌舵，智能体执行** | 关键决策点（push、MR、merge）等待用户确认 |
| **保持历史整洁** | 使用 rebase 保持线性提交历史 |
| **原子性提交** | 一个逻辑变更对应一个 commit |
| **可追溯性** | Commit message 清晰描述意图，MR 关联 Issue |

---

## 前置检查（Agent 必须执行）

在任何操作前，先完成以下检查：

```bash
# 1. 确认 glab 已认证
glab auth status

# 2. 确认当前分支和 remote 配置
git branch --show-current
git remote -v

# 3. 确认目标分支（默认为 main，从 AGENTS.md 或用户确认）
# ⚠️ 如 remote 使用 SSH 且认证失败，需切换 HTTPS：
# git remote set-url origin https://git.n.xiaomi.com/<group>/<repo>.git
```

**Agent 行为**：
- ❌ 若 `glab auth status` 失败 → 停止，告知用户配置认证
- ❌ 若 remote SSH 不可用 → 切换为 HTTPS 后继续
- ⏸️ 确认目标分支后继续

**STOP。** 若前置检查失败，进入 [完成状态](#完成状态) 上报 BLOCKED。

---

## 逃生舱

- **快速查看**：如果用户只说"看看 diff"或"看看状态" → 只执行 `git diff` 或 `git status`，不进入完整流程
- **跳过确认**：如果用户说"直接做"或"跳过确认" → 跳过所有 ⏸️ 确认点，执行完后一次性汇报
- **处理 review**：如果用户只说"处理 review" → 直接跳到 [Phase 10](#10-处理-review-反馈)

---

## Role: Developer

### Phase 1：接收或创建 Issue

```bash
# 查看 issue 详情
glab issue view <issue-number> --repo <group>/<repo>

# （可选）创建新 issue
glab issue create \
  --repo <group>/<repo> \
  --title "<title>" \
  --description "<body>"
```

**Agent 行为**：
- ✅ 读取 issue 内容，理解需求
- 📝 记录 issue 编号，后续 MR 需关联

---

### Phase 2：同步并创建分支（关键步骤）

```bash
# 1. 切到目标分支并拉取最新
git checkout <target-branch>   # 通常为 main
git pull

# 2. 创建功能分支
git checkout -b <type>/<issue-简述>
```

**分支命名规范**：
| Type | 场景 |
|------|------|
| `feat/` | 新功能 |
| `fix/` | Bug 修复 |
| `docs/` | 文档变更 |
| `refactor/` | 重构 |
| `chore/` | 构建/工具变更 |

**分支命名示例**：

GOOD: `fix/config-show-workspaces-null`
GOOD: `feat/user-auth-jwt`
BAD:  `my-branch`（无 type 前缀，无法识别变更类型）
BAD:  `fix`（过于笼统，无具体描述）

**Agent 行为**：
- ⏸️ **创建分支前必须确认目标分支**（从用户或 AGENTS.md 读取）
- ❌ 禁止从非目标分支创建
- ✅ 自动执行 `git checkout <target-branch> && git pull`

**STOP。** 确认目标分支后继续。

---

### Phase 3：开发变更

编辑文件，执行必要的操作。

**Agent 行为**：
- ✅ 按需修改文件
- ✅ 运行 lint + 测试验证（参考项目 AGENTS.md）
- ✅ 修复所有 lint / test 错误后再进入下一步

---

### Phase 4：展示变更（确认点 1）

```bash
git diff
```

**Agent 行为**：
- ⏸️ **停止并等待用户确认**
- 📊 展示所有变更的 diff
- 💬 说明修改意图和影响范围

**用户决策**：
- ✅ 确认 → 继续
- ❌ 拒绝 → 修改后重新展示
- 🔄 调整 → Agent 根据反馈修改

**STOP。** 等待用户确认。

---

### Phase 5：Rebase 到最新基线

```bash
git fetch origin
git log HEAD..<target-branch> --oneline   # 检查是否有新提交
# 如有新提交：
git rebase <target-branch>
```

**Agent 行为**：
- ✅ 先 `git fetch origin` 获取最新状态
- ⚠️ 如有冲突 → 立即停止，报告冲突文件，等待用户手动解决

**STOP。** rebase 冲突时必须停止，等待用户手动解决。

---

### Phase 6：提交变更

```bash
git add <相关文件>       # 精确暂存，避免 git add .
git commit -m "<type>(<scope>): <description> (#<issue-number>)"
```

**Commit Message 格式**：
```
<type>(<scope>): <subject> (#issue)

[optional body]
```

**Commit Message 示例**：

GOOD: `fix(config): resolve null pointer when workspace missing (#123)`
GOOD: `feat(auth): implement JWT-based user authentication (#456)`
BAD:  `fix bug`（无 scope、无 issue 关联、无具体描述）
BAD:  `update code`（过于笼统，无法理解变更意图）

**Agent 行为**：
- ✅ 自动生成符合规范的 commit message
- ✅ 只暂存与本次变更相关的文件
- 📝 Subject 不超过 50 字符
- 📝 Body 说明变更原因（如需要）

---

### Phase 7：展示提交（确认点 2）

```bash
git show HEAD --stat
```

**Agent 行为**：
- ⏸️ **停止并等待用户确认**
- 📊 展示 commit message、变更文件列表

**用户决策**：
- ✅ 确认 → 继续推送
- ❌ 修改 → `git commit --amend` 调整

**STOP。** 等待用户确认。

---

### Phase 8：推送到远端（确认点 3）

```bash
git push -u origin <branch-name>    # 首次推送
git push origin <branch-name>       # 后续推送
```

**Agent 行为**：
- ⏸️ **停止并展示推送信息**：
  - 分支名
  - 远程仓库 URL
  - 即将推送的 commit 数量和 hash
- 💬 询问："是否确认推送到 origin？"
- ⏸️ **等待用户明确确认**

**用户决策**：
- ✅ 确认 → 执行推送
- ❌ 取消 → 保留本地 commit

**STOP。** 等待用户确认。

---

### Phase 9：创建 MR（确认点 4）

```bash
glab mr create \
  --source-branch <branch-name> \
  --target-branch <target-branch> \
  --title "<type>(<scope>): <description>" \
  --description "$(cat <<'EOF'
## Changes
- 变更点 1
- 变更点 2

## Motivation
变更原因

## Closes
Closes #<issue-number>

## Testing
- [x] 已通过本地测试
- [x] 已通过 lint 检查
EOF
)"
```

**Agent 行为**：
- ⏸️ **停止并展示 MR 信息，等待用户最终确认**
- 📊 展示：标题、目标分支、描述、关联 issue
- 💬 确认 target branch 是否正确

**用户决策**：
- ✅ 确认 → 创建 MR
- ❌ 取消 → 不创建
- 🔄 调整 → 修改后重新展示

**STOP。** 等待用户确认。

---

<a id="10-处理-review-反馈"></a>
### Phase 10：处理 Review 反馈

收到 review 后的循环：

```bash
# 1. 查看 MR 评论
glab mr view <mr-number> --repo <group>/<repo>
glab mr diff <mr-number> --repo <group>/<repo>

# 2. 根据反馈修改代码

# 3. 提交修改（在同一条分支上）
git add <files>
git commit -m "fix: <描述修复内容>"
git push origin <branch-name>

# 4. 通知 reviewer（MR 会自动更新）
```

**Agent 行为**：
- ✅ 读取 review 评论并理解修改要求
- ✅ 在同一分支上修改，保持 commit 历史清晰
- ⏸️ 每次提交前展示变更，等待用户确认
- 🔁 持续循环直到 MR 被合并或关闭

---

## Role: Reviewer

### Phase 1：Review MR

```bash
# 查看 MR 详情
glab mr view <mr-number> --repo <group>/<repo>

# 查看 diff
glab mr diff <mr-number> --repo <group>/<repo>

# 查看 MR 中的讨论
glab mr note list <mr-number> --repo <group>/<repo>
```

**Review 检查清单**：
- [ ] 代码是否符合项目规范（lint / format）
- [ ] 测试是否覆盖变更
- [ ] 是否关联了对应 Issue
- [ ] Commit message 是否清晰
- [ ] 功能是否满足 Issue 需求

---

### Phase 2：给出 Review 建议

```bash
# 在 MR 中添加评论
glab mr note <mr-number> --repo <group>/<repo> --message "<review 意见>"

# 或者在特定文件添加行级评论
glab api \
  --method POST \
  "projects/<project-id>/merge_requests/<mr-iid>/notes" \
  -f body="<评论内容>"
```

**Agent 行为**：
- ⏸️ **展示 review 意见，等待用户确认后再提交**
- 💬 提出具体修改建议

**STOP。** 等待用户确认。

---

### Phase 3：合并 MR（确认点）

当 MR 符合期望时：

```bash
# 查看最终状态
glab mr view <mr-number> --repo <group>/<repo>

# 合并 MR
glab mr merge <mr-number> --repo <group>/<repo>
```

**合并前检查**：
- [ ] 所有 review 意见已解决
- [ ] CI pipeline 通过（如配置了）
- [ ] 无冲突

**Agent 行为**：
- ⏸️ **展示合并信息，等待用户最终确认**

**STOP。** 等待用户确认。

---

### Phase 4：Release 流程

合并到目标分支后，执行 release（按项目 AGENTS.md 规范）：

```bash
# 1. 切到目标分支并拉取最新
git checkout <target-branch>
git pull

# 2. 更新版本号（如需要）
# 编辑 src/<package>/__init__.py

# 3. 创建 tag
git tag v<version>
git push origin v<version>

# 4. 创建 GitLab Release
glab release create v<version> \
  --repo <group>/<repo> \
  --name "v<version>" \
  --notes "$(cat <<'EOF'
## Changes
- 变更摘要
EOF
)"
```

**Agent 行为**：
- ⏸️ **每个步骤前展示信息，等待用户确认**
- 📝 版本号遵循语义化版本（SemVer）
- 📝 Release notes 从 commit log 和 Issue 中生成

**STOP。** 每个步骤前等待用户确认。

---

## 自我调节

- 连续 3 次 git 操作失败 → **STOP**，上报用户
- MR 创建失败超过 2 次 → **STOP**，检查 remote 配置
- rebase 冲突 → **STOP**，等待用户手动解决
- 单次流程超过 15 分钟无进展 → **STOP**，评估是否需要用户介入

上报格式：
```
STATUS: BLOCKED
REASON: [1-2 句话]
ATTEMPTED: [已尝试的方法]
RECOMMENDATION: [建议用户下一步]
```

---

## 完整流程示例

### Developer 流程

```bash
# 前置检查
glab auth status

# 1. 读取 issue
glab issue view 1 --repo olap/kyuubi-cli

# 2. 同步并创建分支
git checkout main && git pull
git checkout -b fix/some-bug

# 3. 开发 & 测试
# ... 修改代码 ...
uv run ruff check src tests
uv run pytest

# 4. 展示变更（确认点 1）
git diff
# 👤 等待用户确认

# 5. Rebase
git fetch origin && git rebase main

# 6. 提交
git add <files>
git commit -m "fix(scope): description (#1)"

# 7. 展示提交（确认点 2）
git show HEAD --stat
# 👤 等待用户确认

# 8. 推送（确认点 3）
# 👤 等待用户确认
git push -u origin fix/some-bug

# 9. 创建 MR（确认点 4）
# 👤 等待用户确认
glab mr create --source-branch fix/some-bug --target-branch main ...

# 10. 处理 review（循环）
# ... 收到反馈 → 修改 → 推送 ...
```

### Reviewer 流程

```bash
# 1. 查看 MR
glab mr view 3 --repo olap/kyuubi-cli
glab mr diff 3 --repo olap/kyuubi-cli

# 2. 给出意见或合并
# 👤 确认后执行
glab mr merge 3 --repo olap/kyuubi-cli

# 3. Release
git checkout main && git pull
git tag v0.1.1 && git push origin v0.1.1
glab release create v0.1.1 --repo olap/kyuubi-cli --name "v0.1.1" --notes "..."
```

---

## 异常处理

### Push 失败（SSH 认证问题）

```bash
# 切换到 HTTPS
git remote set-url origin https://git.n.xiaomi.com/<group>/<repo>.git
git push -u origin <branch-name>
```

### MR 目标分支错误

```bash
# 关闭错误的 MR
glab mr close <wrong-mr-number> --repo <group>/<repo>

# 重新创建正确的 MR
glab mr create --target-branch <correct-branch> ...
```

### Merge 冲突

```bash
git fetch origin
git rebase <target-branch>
# 👤 用户手动解决冲突后
git add <resolved-files>
git rebase --continue
git push origin <branch-name> --force-with-lease
```

---

## Checklist：Agent 自检清单

执行 Git 操作前，Agent 必须确认：

- [ ] **前置检查**：`glab auth status` 通过
- [ ] **Remote 配置**：remote URL 可访问（HTTPS 或 SSH）
- [ ] **目标分支**：明确 MR 应 target 哪个分支
- [ ] **分支起点**：分支从目标分支的最新 HEAD 创建
- [ ] **Issue 关联**：commit message 和 MR 描述中关联 Issue
- [ ] **确认节点**：识别需要用户确认的关键步骤（push、MR、merge、release）
- [ ] **回滚方案**：知道如何撤销操作

---

## 完成状态

- **DONE** — 流程全部完成（代码已合并或 MR 已创建）
- **DONE_WITH_CONCERNS** — 完成但有待确认（如 CI 未通过、review 未完成）
- **BLOCKED** — 无法继续（认证失败、冲突未解决）
- **NEEDS_CONTEXT** — 缺少信息（目标分支、issue 编号、repo 路径）

---

## Philosophy

> Git 历史是团队协作的因果记录。每一次 MR 都应该是清晰、原子、可追溯的状态转换。
>
> Developer 负责实现，Reviewer 负责把关。两者协同，保证代码质量。

---

**Skill Version**: 1.1.0
**Author**: kyuubi-cli
**Status**: Active & Enforced
**Last Updated**: 2026-03-25
