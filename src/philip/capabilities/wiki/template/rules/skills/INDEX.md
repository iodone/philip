# Skills Index

本索引指向可复用的 Skills（技能）—— AI 可以调用的工具、流程和最佳实践。

- **想使用某个能力** → 浏览下方分类，找到对应的 skill 文件
- **想添加新 skill** → 参考现有文件格式，添加到对应分类

---

## 分类索引

### Workflow（工作流）

特定任务的完整工作流程。

- [深度调研工作流](../../.agents/skills/workflow-deep-research-survey/SKILL.md) ✅ — 多 Agent 并行 + 交叉验证（Phase 1-3 信息采集）。**不用**：快速事实核查/单点查询——直接搜索，不启动多 Agent 流程
- [分析写作工作流](../../.agents/skills/workflow-analytical-writing/SKILL.md) ✅ — 将调研素材转化为有判断力的分析文章。包含 Thesis Catalog（核心分析视角 L1-L6）和判断合成步骤。**做深度调研并写 external 文章时，两个 skill 都要读**。**不用**：素材未经验证先走 deep-research-survey；内部纪要直接写 contexts/
- [GitHub PR 工作流](../../.agents/skills/workflow-github/SKILL.md) ✅ — 基于 `gh` CLI 管理分支、提交、PR、review、merge 的完整协作流程。**不用**：GitLab 等非 GitHub 托管仓库（本流程基于 gh CLI）
- [LLM Wiki 工作流](../../.agents/skills/workflow-llm-wiki/SKILL.md) ✅ — 负责 wiki 的 ingest、query、lint、research，输入层统一来自 `contexts/`。**不用**：日常沉淀写 contexts/；wiki 变更走本 skill 命令，不手工维护页面
- [YC Office Hours](../../.agents/skills/workflow-office-hours/SKILL.md) ✅ — 产品诊断与设计思维头脑风暴。Startup 模式：六个逼问暴露需求真相；Builder 模式：side project 设计伙伴。产出设计文档，不写代码。**不用**：已决定要做、要 spec → spark；纯技术实现讨论
- [Spark](../../.agents/skills/workflow-spark/SKILL.md) ✅ — 头脑风暴 → 设计 spec。逐个问题探索意图，提出 2-3 种方案，写 spec 到 `contexts/thought_review/` 后 STOP，不自动链到实现。**不用**：还在判断值不值得做 → 先 office-hours
- [ELI5 极简讲解](../../.agents/skills/workflow-eli5/SKILL.md) ✅ — 用大图 + 极少文字把任何主题讲给零基础的人。用户输入 `/eli5 <topic>` 或要求"像 5 岁小孩一样解释"时使用，产出自包含 HTML artifact（一图一句，日常类比作骨架）。**不用**：受众需要精确技术细节时（类比骨架刻意牺牲精度）

### Guide（指南）

领域实现手册和技术指南。

- [Scala Direct Style 指南](../../.agents/skills/guide-scala-direct-style/SKILL.md) ✅ — Scala 3 / Tapir / Ox 直风格后端开发指南。**不用**：Scala 2 / ZIO / cats-effect 栈（本指南假设 direct style）

### Guard（守卫）

安全和约束型守卫 skill。

- [安全守卫](../../.agents/skills/guard-security/SKILL.md) ✅ — Bash、网络、文件写入、敏感输出前的零信任检查。**不用**：纯讨论安全概念、不涉及实际操作时

### Analyzer（分析器）

结构化分析和诊断类 skill。

- [结构稳定性分析器](../../.agents/skills/analyzer-structural-stability/SKILL.md) ✅ — 判断一个结构能否长期存活。**不用**：要判断对错/真伪时——它只判结构能否存活

### Tool（工具）

工具使用方法和最佳路径

- [Skill 优化器](../../.agents/skills/tool-skill-optimizer/SKILL.md) ✅ — 诊断并重写 SKILL.md 结构。**不用**：从零建新 skill → skill-creator；一两行小修不跑 7 维诊断

---

## 如何添加你自己的 Skill

1. skill 存放位置在 `.agents/skills/` 目录
2. 参考现有 skill 文件的格式（元数据、核心说明、使用步骤、示例）
3. description 必须同时写清「何时不用」：点名真实的混淆对和替代路径（例：还在判断值不值得做 → 先 office-hours，不走 spark）——skill 被错误触发比不被触发更贵
4. 以 `<category>-<name>` 命名目录（例如 `workflow-my-process`、`bestpractice-my-insight`）
5. 分类前缀按能力类型选择，不要随意混用：
   - `workflow-`：分阶段执行流，适合有明确输入、步骤、产出的完整工作流
   - `tool-`：可直接调用的工具能力，适合封装单点能力或操作接口
   - `bestpractice-`：方法论、经验法则、判断原则
   - `guide-`：领域实现指南、技术手册、框架约定
   - `guard-`：安全守卫、约束检查、风险拦截
   - `analyzer-`：分析器、诊断器、评估器
6. 在 INDEX.md 对应分类下添加一行（含「不用」条款）

可以使用 `skill-creator` skill 创建新的 skill，格式参考（最简版）：

```markdown
# Skill: 名称

## When to Use
什么情况下触发这个 skill

## When NOT to Use
何时不应使用——点名混淆对与替代路径

## Prerequisites
需要什么工具/配置

## 步骤
1. 步骤一
2. 步骤二
```

## Progressive Disclosure

Skills 采用渐进式披露原则：
- **INDEX.md** 提供概览，快速定位
- **具体 skill 文件** 包含完整的操作步骤和示例
