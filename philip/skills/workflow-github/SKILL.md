---
name: workflow-github
description: |
  GitHub PR 工作流程 skill，使用 gh CLI 管理完整的 Developer/Reviewer 流程。
  支持两种协作模式：Fork-upstream（有上游仓库）和 Same-repo（直接在主仓库开发）。
  当用户提到以下场景时必须使用：创建分支、提交代码、创建 PR、review 代码、
  合并 PR、release、处理 review 反馈、git workflow、代码协作、PR 流程。
  即使用户只说"帮我提个 PR"或"review 一下这个分支"也要触发。
---

**HARD GATE：** 本 skill 只做 GitHub PR 工作流程管理。
不执行业务代码逻辑，不修改非 git 相关文件，不代替用户做最终决策。
所有 push、PR、merge、release 操作必须等待用户确认。

---

# GitHub Workflow Skill (gh)

基于 `gh` CLI 的 GitHub 协作工作流程，定义 **Developer** 和 **Reviewer** 两个角色。

## 核心原则

| 原则 | 实践 |
| :--- | :--- |
| **人类掌舵，智能体执行** | 关键决策点（push、PR、merge）等待用户确认 |
| **保持历史整洁** | 使用 rebase 保持线性提交历史 |
| **原子性提交** | 一个逻辑变更对应一个 commit |
| **可追溯性** | Commit message 清晰描述意图，PR 关联 Issue |

---

## 前置检查（Agent 必须执行）

在任何操作前，先完成以下检查：

```bash
# 1. 确认 gh 已认证
gh auth status

# 2. 确认当前仓库和 remote 配置
gh repo view
git remote -v

# 3. 判断协作模式（关键！）
git remote get-url upstream 2>/dev/null && echo "FORK-UPSTREAM 模式" || echo "SAME-REPO 模式"

# 4. 确认目标分支（默认为 main，从 AGENTS.md 或用户确认）
```

**协作模式判断**：

| 模式 | 特征 | 同步方式 |
|------|------|----------|
| **Fork-upstream** | 有 `upstream` remote | `gh repo sync` 或 `git pull upstream main` |
| **Same-repo** | 无 `upstream`，只有 `origin` | `git pull origin main` 或 `git fetch origin` |

**Agent 行为**：
- ❌ 若 `gh auth status` 失败 → 停止，告知用户配置认证
- ❌ 若 remote 不可达 → 停止，检查 URL 或网络
- ✅ **自动检测协作模式**，后续流程根据模式调整
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
gh issue view <issue-number>

# （可选）创建新 issue
gh issue create \
  --title "<title>" \
  --body "<body>"
```

**Agent 行为**：
- ✅ 读取 issue 内容，理解需求
- 📝 记录 issue 编号，后续 PR 需关联

---

### Phase 2：获取代码并同步（关键步骤）

**如果本地还没有仓库**（初次获取代码）：

```bash
# ===== Fork-upstream 模式（推荐）=====
gh repo clone <your-fork-repo>
# gh 会自动检测 fork 关系并配置 upstream remote

# ===== Same-repo 模式 =====
gh repo clone <repo>
# 直接 clone 主仓库
```

**如果本地已有仓库**（同步最新代码）：

```bash
# ===== Fork-upstream 模式 =====
# 方式 1：使用 gh 自动同步（推荐）
gh repo sync

# 方式 2：手动同步
git checkout <target-branch>
git pull upstream <target-branch>
git push origin <target-branch>

# ===== Same-repo 模式（无 upstream）=====
git checkout <target-branch>
git pull origin <target-branch>
# 或 fetch 后 rebase
git fetch origin
git rebase origin/<target-branch>
```

**同步完成后创建分支**：
```bash
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
- ✅ Fork-upstream 模式优先使用 `gh repo sync`
- ✅ Same-repo 模式使用 `git pull origin <target-branch>`

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
# ===== Fork-upstream 模式 =====
git fetch upstream
git log HEAD..<target-branch> --oneline
# 如有新提交：
git rebase <target-branch>

# ===== Same-repo 模式 =====
git fetch origin
git log HEAD..<target-branch> --oneline
# 如有新提交：
git rebase <target-branch>
# 或 rebase 到 origin/<target-branch>
git rebase origin/<target-branch>
```

**Agent 行为**：
- ✅ 根据协作模式选择 fetch 来源（upstream 或 origin）
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

### Phase 9：创建 PR（确认点 4）

```bash
gh pr create \
  --base <target-branch> \
  --head <branch-name> \
  --title "<type>(<scope>): <description>" \
  --body "$(cat <<'EOF'
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

**GitHub PR 特有选项**（按需使用）：
```bash
# 创建 Draft PR（标记为工作进行中）
gh pr create --draft ...

# 指定 reviewer
gh pr create --reviewer <username> ...

# 指定 assignee
gh pr create --assignee <username> ...

# 添加 label
gh pr create --label bug,enhancement ...
```

**Agent 行为**：
- ⏸️ **停止并展示 PR 信息，等待用户最终确认**
- 📊 展示：标题、目标分支、描述、关联 issue
- 💬 确认 base branch 是否正确

**用户决策**：
- ✅ 确认 → 创建 PR
- ❌ 取消 → 不创建
- 🔄 调整 → 修改后重新展示

**STOP。** 等待用户确认。

---

<a id="10-处理-review-反馈"></a>
### Phase 10：处理 Review 反馈

收到 review 后的循环：

```bash
# 1. 查看 PR 详情和评论
gh pr view
gh pr diff

# 2. 查看 review 评论
gh pr review --list    # 列出所有 review
gh api repos/{owner}/{repo}/pulls/<pr-number>/comments  # 行级评论

# 3. 根据反馈修改代码

# 4. 提交修改（在同一条分支上）
git add <files>
git commit -m "fix: <描述修复内容>"
git push origin <branch-name>

# 5. 回复 review 评论（如需要）
gh pr comment <pr-number> --body "已修复：<说明>"
```

**Agent 行为**：
- ✅ 读取 review 评论并理解修改要求
- ✅ 在同一分支上修改，保持 commit 历史清晰
- ⏸️ 每次提交前展示变更，等待用户确认
- 🔁 持续循环直到 PR 被合并或关闭

---

## Role: Reviewer

### Phase 1：Review PR

```bash
# 查看 PR 详情
gh pr view <pr-number>

# 查看 diff
gh pr diff <pr-number>

# 查看 PR 中的 commits
gh pr view <pr-number> --json commits
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
# 在 PR 中添加评论
gh pr comment <pr-number> --body "<review 意见>"

# 提交 review（approve / request-changes / comment）
gh pr review <pr-number> --approve --body "LGTM 👍"
gh pr review <pr-number> --request-changes --body "需要修改：<说明>"
gh pr review <pr-number> --comment --body "<一般评论>"
```

**Agent 行为**：
- ⏸️ **展示 review 意见，等待用户确认后再提交**
- 💬 提出具体修改建议

**STOP。** 等待用户确认。

---

### Phase 3：合并 PR（确认点）

当 PR 符合期望时：

```bash
# 查看最终状态
gh pr view <pr-number>

# 合并 PR（支持多种合并方式）
gh pr merge <pr-number>                    # 默认 squash merge
gh pr merge <pr-number> --merge            # 创建 merge commit
gh pr merge <pr-number> --rebase           # rebase 后合并（保持线性）
gh pr merge <pr-number> --delete-branch    # 合并后删除分支
```

**合并前检查**：
- [ ] 所有 review 意见已解决
- [ ] CI checks 通过（如配置了）
- [ ] 无冲突
- [ ] 已获得至少一个 approve

**Agent 行为**：
- ⏸️ **展示合并信息和合并方式，等待用户最终确认**
- 💬 建议使用哪种合并方式（squash/merge/rebase）

**STOP。** 等待用户确认。

---

### Phase 4：Release 流程

合并到目标分支后，执行 release（按项目 AGENTS.md 规范）：

```bash
# ===== Fork-upstream 模式 =====
git checkout <target-branch>
git pull upstream <target-branch>
git tag v<version>
git push upstream v<version>

# ===== Same-repo 模式 =====
git checkout <target-branch>
git pull origin <target-branch>
git tag v<version>
git push origin v<version>

# 创建 GitHub Release（两种模式相同）
gh release create v<version> \
  --title "v<version>" \
  --notes "$(cat <<'EOF'
## Changes
- 变更摘要
EOF
)" \
  --draft  # 先创建草稿，确认后再发布
```

**Agent 行为**：
- ⏸️ **每个步骤前展示信息，等待用户确认**
- 📝 版本号遵循语义化版本（SemVer）
- 📝 Release notes 从 commit log 和 Issue 中生成
- ✅ 根据协作模式选择 push 目标（upstream 或 origin）

**STOP。** 每个步骤前等待用户确认。

---

## 自我调节

- 连续 3 次 git 操作失败 → **STOP**，上报用户
- PR 创建失败超过 2 次 → **STOP**，检查 remote 配置
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

### Developer 流程（Fork-upstream 模式）

```bash
# 前置检查
gh auth status
gh repo view
git remote get-url upstream  # 确认有 upstream

# 1. 读取 issue
gh issue view 1

# 2. 同步并创建分支
gh repo sync
git checkout -b fix/some-bug

# 3. 开发 & 测试
# ... 修改代码 ...
npm run lint
npm test

# 4. 展示变更（确认点 1）
git diff
# 👤 等待用户确认

# 5. Rebase
git fetch upstream && git rebase main

# 6. 提交
git add <files>
git commit -m "fix(scope): description (#1)"

# 7. 展示提交（确认点 2）
git show HEAD --stat
# 👤 等待用户确认

# 8. 推送（确认点 3）
# 👤 等待用户确认
git push -u origin fix/some-bug

# 9. 创建 PR（确认点 4）
# 👤 等待用户确认
gh pr create --base main --title "fix(scope): description" --body "..."

# 10. 处理 review（循环）
# ... 收到反馈 → 修改 → 推送 ...
```

### Developer 流程（Same-repo 模式）

```bash
# 前置检查
gh auth status
gh repo view
git remote -v  # 确认只有 origin，无 upstream

# 1. 读取 issue
gh issue view 1

# 2. 同步并创建分支
git checkout main
git pull origin main
git checkout -b fix/some-bug

# 3. 开发 & 测试
# ... 修改代码 ...
npm run lint
npm test

# 4. 展示变更（确认点 1）
git diff
# 👤 等待用户确认

# 5. Rebase
git fetch origin && git rebase origin/main

# 6. 提交
git add <files>
git commit -m "fix(scope): description (#1)"

# 7. 展示提交（确认点 2）
git show HEAD --stat
# 👤 等待用户确认

# 8. 推送（确认点 3）
# 👤 等待用户确认
git push -u origin fix/some-bug

# 9. 创建 PR（确认点 4）
# 👤 等待用户确认
gh pr create --base main --title "fix(scope): description" --body "..."

# 10. 处理 review（循环）
# ... 收到反馈 → 修改 → 推送 ...
```

### Reviewer 流程

```bash
# 1. 查看 PR
gh pr view 3
gh pr diff 3

# 2. 给出意见或合并
# 👤 确认后执行
gh pr review 3 --approve --body "LGTM"
gh pr merge 3 --squash --delete-branch

# 3. Release（按协作模式选择）
# Fork-upstream:
git checkout main && git pull upstream main
git tag v0.1.1 && git push upstream v0.1.1

# Same-repo:
git checkout main && git pull origin main
git tag v0.1.1 && git push origin v0.1.1

gh release create v0.1.1 --title "v0.1.1" --notes "..."
```

---

## 异常处理

### Push 失败（认证问题）

```bash
# 检查认证
gh auth status

# 重新认证
gh auth login

# 或使用 token
gh auth login --with-token < token.txt
```

### PR 目标分支错误

```bash
# 关闭错误的 PR
gh pr close <wrong-pr-number>

# 重新创建正确的 PR
gh pr create --base <correct-branch> ...
```

### Merge 冲突

```bash
# 根据协作模式 fetch
git fetch upstream  # Fork-upstream 模式
# 或
git fetch origin    # Same-repo 模式

git rebase <target-branch>
# 👤 用户手动解决冲突后
git add <resolved-files>
git rebase --continue
git push origin <branch-name> --force-with-lease
```

### PR 更新（补充提交）

```bash
# 在已有分支上继续提交
git add <files>
git commit -m "fix: <补充说明>"
git push origin <branch-name>   # PR 自动更新

# 修改最后一次 commit message
git commit --amend -m "fix(scope): updated message"
git push origin <branch-name> --force-with-lease
```

---

## Checklist：Agent 自检清单

执行 Git 操作前，Agent 必须确认：

- [ ] **前置检查**：`gh auth status` 通过
- [ ] **协作模式**：检测并确认是 Fork-upstream 还是 Same-repo 模式
- [ ] **Remote 配置**：remote URL 可访问
- [ ] **目标分支**：明确 PR 应 target 哪个分支
- [ ] **分支起点**：分支从目标分支的最新 HEAD 创建
- [ ] **Issue 关联**：commit message 和 PR 描述中关联 Issue
- [ ] **确认节点**：识别需要用户确认的关键步骤（push、PR、merge、release）
- [ ] **回滚方案**：知道如何撤销操作

---

## 完成状态

- **DONE** — 流程全部完成（代码已合并或 PR 已创建）
- **DONE_WITH_CONCERNS** — 完成但有待确认（如 CI 未通过、review 未完成）
- **BLOCKED** — 无法继续（认证失败、冲突未解决）
- **NEEDS_CONTEXT** — 缺少信息（目标分支、issue 编号、repo 路径）

---

## Philosophy

> Git 历史是团队协作的因果记录。每一次 PR 都应该是清晰、原子、可追溯的状态转换。
>
> Developer 负责实现，Reviewer 负责把关。两者协同，保证代码质量。

---

**Skill Version**: 1.1.0
**Author**: Meta42
**Status**: Active & Enforced
**Last Updated**: 2026-03-30
**Modes**: Fork-upstream + Same-repo
