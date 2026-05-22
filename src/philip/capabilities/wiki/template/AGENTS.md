# AGENTS.md - Your Workspace

This folder is home. Treat it that way.

---

## 1. Every Session

Before doing anything else:

1. Read `rules/SOUL.md` — this is who you are
2. Read `rules/USER.md` — this is who you're helping
3. Read `rules/WORKSPACE.md` — file routing table, check before searching for files
5. Read `rules/COMMUNICATION.md` — how to think and communicate (especially for non-coding tasks)
6. Read `rules/skills/INDEX.md` — understand available skills
7. Read `rules/SECURITY.md` — security rules for commands, file writes, network requests, and external output

Don't ask permission. Just do it.

---

## 2. File Routing

### 2.1 文件查找

**找文件时，先查 `rules/WORKSPACE.md`，再搜索。** WORKSPACE.md 是这个 workspace 的目录索引，记录了每类内容的存放位置。绝大多数情况下查一下就能定位到目标目录，不需要全盘 glob/grep。如果发现新目录或项目没被收录，顺手更新 WORKSPACE.md。

### 2.2 沉淀类内容路由

**做”沉淀 / 纪要 / 讨论整理 / 记忆写入”时，默认写入当前 workspace 的 `contexts/`。**

- 所有需要长期保留、后续可继续加工的材料，都应该落在当前仓库的 `contexts/`。

**沉淀类内容的路由约定：**

- 当天发生了什么、群聊纪要、决策摘要、待跟进事项 → `contexts/daily_records/`
- 深度分析、架构讨论、方法论拆解、成熟对话整理 → `contexts/thought_review/`
- 围绕一个主题的一轮调研、资料筛选、阶段性结论 → `contexts/survey_sessions/`
- 外部文章、网页、文档原文摘录 → `contexts/clippings/`

**命名示例：**

- `AI Agent 记忆系统讨论沉淀` 这类整理稿，默认应写到 `contexts/thought_review/2026-05-09-agent-memory-discussion.md`

---

## 3. Skills

**Skills** 是 AI 可复用的能力，包括工作流、工具、最佳实践、指南、守卫、分析器等。

**重要：遇到"怎么做 X"时，先查 skill 再查系统工具。** 搜索顺序：(1) 下方速查表 → (2) `rules/skills/INDEX.md` → (3) 系统工具。

**需要执行某项任务** → 先查 `rules/skills/INDEX.md` 找到对应的 skill  
**想添加新能力** → 参考现有 skill 格式，更新 INDEX.md

### 3.1 常用 Skill 速查（以 INDEX.md 为准）

**深度调研任务** → `.agents/skills/workflow-deep-research-survey/SKILL.md`  
- 初步扫描 → 分割维度 → 多 Agent 并行 → 交叉验证 → 写报告  
- 输出：`contexts/survey_sessions/`

**调用后台 Agent / 并行 Subagent** → `.agents/skills/workflow-parallel-subagents/SKILL.md`  
- 何时拆分任务、如何并行派出多个 subagent  
- 准备调用 `run_in_background=True` 前，先把这个 skill 读一遍再执行  
- 派出 agent 后等系统通知即可，不需要轮询

**维护 Wiki** → `.agents/skills/workflow-llm-wiki/SKILL.md`  
- 负责 wiki 的 ingest / query / lint / research  
- 输入层来自 `contexts/`，稳定知识写入 `wiki/`
- 只要任务是在**ingest、生成、更新、刷新 wiki 内容**，默认必须走这个 skill；不要手动写 wiki 页面、目录页、索引页来代替 ingest
- 说明：wiki 的目标是把 `contexts/` 里的材料结晶为稳定知识，而不是手工维护一个”看起来更新了”的目录。绕过 ingest 会跳过筛选、溯源、日志和 sync，结构上是不完整的

**产品诊断 / 设计头脑风暴** → `.agents/skills/workflow-office-hours/SKILL.md`
- Startup 模式：六个逼问（需求现实、现状、精准用户、最窄切口、观察、未来适配）
- Builder 模式：side project / hackathon 设计伙伴
- 产出设计文档 → `contexts/thought_review/`，不写代码

---

## 4. Output Quality Standards

⚠️ **有竞品在围观**，所有输出必须严谨、专业、符合规范。

### 4.1 Quality Checklist

- [ ] 结构清晰，层级分明
- [ ] 命名一致，使用 kebab-case
- [ ] 无冗余信息，每一句话都有价值
- [ ] 专业术语准确，不偷懒不敷衍
- [ ] 代码示例可直接运行
- [ ] 文档间关联明确（使用 `links` 字段）

---

## 5. Coding Discipline

> 来源：Andrej Karpathy — 减少常见 LLM 编码错误的行为准则。与项目规范冲突时，以项目规范为准。

### 5.1 先想再写

**不假设。不隐藏困惑。暴露权衡。**

实现之前：
- 明确陈述假设，不确定就问
- 存在多种解读时全部列出，不要悄悄选一个
- 有更简单的方案就直说，该推回就推回
- 不清楚的地方停下来，说清楚哪里不懂，再问

### 5.2 简洁优先

**最小代码解决问题，不做投机性设计。**

- 不做没要求的功能
- 不为只用一次的代码建抽象
- 不加没要求的"灵活性"和"可配置性"
- 不为不可能的场景写错误处理
- 200 行能缩成 50 行，就重写

自问：「资深工程师会觉得这过度设计吗？」是就简化。

### 5.3 精准改动

**只碰必须碰的。只收拾自己制造的烂摊子。**

编辑已有代码时：
- 不"顺手改进"相邻代码、注释或格式
- 不重构没坏的东西
- 匹配现有风格，即使你会写得不同
- 发现不相关的死代码，提一嘴但不删

你的改动产生孤立引用时：
- 删掉你造成的无用 import/变量/函数
- 不删已有的死代码，除非被要求

判断标准：每一行改动都能追溯到用户的请求。

### 5.4 目标驱动执行

**定义验收标准，循环直到验证通过。**

把任务转化为可验证的目标：
- "加校验" → "写无效输入的测试，然后通过"
- "修 bug" → "写复现测试，然后通过"
- "重构 X" → "确保改动前后测试都通过"

多步任务先列简要计划：
```
1. [步骤] → 验证: [检查项]
2. [步骤] → 验证: [检查项]
```

强验收标准让 agent 能独立循环；弱标准（"搞定就行"）需要反复确认。

---

## 6. Axioms（公理）

从个人经历提炼的决策原则，用于启发深度思考。分类索引、使用指南和触发词见 `rules/axioms/INDEX.md`。

---

## 7. Memory System（记忆系统）

三层记忆架构：
- **L3（全局约束）**：`rules/` 下的所有文件，每次 session 被动加载
- **L1/L2（动态记忆）**：`contexts/memory/OBSERVATIONS.md`，agent 主动检索
- **自动积累**：定时调度，hearbeat 每日 observer + 每周 reflector


---

## 8. Safety

Use `rules/SECURITY.md` as the source of truth for security decisions.
