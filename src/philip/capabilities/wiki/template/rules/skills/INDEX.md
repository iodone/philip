# Skills Index

本索引指向可复用的 Skills（技能）—— AI 可以调用的工具、流程和最佳实践。

- **想使用某个能力** → 浏览下方分类，找到对应的 skill 文件
- **想添加新 skill** → 参考现有文件格式，添加到对应分类

---

## 分类索引

### Workflow（工作流）

特定任务的完整工作流程。

- [并行 Subagent 工作流](../../.agents/skills/workflow-parallel-subagents/SKILL.md) ✅ — 调用后台 agent、并行执行多个 subagent
  - **必读**：初次使用并行 subagent 前，必须先读此 skill
  - **禁止轮询**：agent 运行期间不要反复调用 `background_output`，系统会自动通知
  - 判断标准：任务可拆分为 ≥2 个子任务，每个 ≥5 tool calls
  - 核心参数：并行度 ≤5，调研 overlap 30-50%，代码 overlap 0-20%
- [深度调研工作流](../../.agents/skills/workflow-deep-research-survey/SKILL.md) ✅ — 多 Agent 并行 + 交叉验证（Phase 1-3 信息采集）
- [分析写作工作流](../../.agents/skills/workflow-analytical-writing/SKILL.md) ✅ — 将调研素材转化为有判断力的分析文章。包含 Thesis Catalog（核心分析视角 L1-L6）和判断合成步骤。**做深度调研并写 external 文章时，两个 skill 都要读**
- [认知画像提取工作流](../../.agents/skills/workflow-cognitive-profile-extraction/SKILL.md) — 从非结构化对话数据提取可预测的认知公理
  - 适用：群聊/Slack/Discord/邮件/播客转录等任意对话数据
  - 流程：广泛扫描 → 深度验证 → 压力测试 → 定稿（≥3 轮动态滚动）
  - **要求 Opus 模型**：写作由 Opus 亲自完成，调研全部 delegate + 并行
- [GitHub PR 工作流](../../.agents/skills/workflow-github/SKILL.md) ✅ — 基于 `gh` CLI 管理分支、提交、PR、review、merge 的完整协作流程
- [知识飞轮设计模式](../../.agents/skills/workflow-knowledge-flywheel/SKILL.md) — 笨数据+笨方法+笨模型=精知识
- [LLM Wiki 工作流](../../.agents/skills/workflow-llm-wiki/SKILL.md) ✅ — 负责 wiki 的 ingest、query、lint、research，输入层统一来自 `contexts/`
- [内容发布工作流](../../.agents/skills/workflow-publish/SKILL.md) ⚙️ — 将 MD 报告转 HTML 发布到你自己的服务器，返回 URL
- [视频下载与语音识别工作流](../../.agents/skills/workflow-bilibili-whisper-transcription/SKILL.md) — Bilibili/YouTube 视频处理
- [YC Office Hours](../../.agents/skills/workflow-office-hours/SKILL.md) ✅ — 产品诊断与设计思维头脑风暴。Startup 模式：六个逼问暴露需求真相；Builder 模式：side project 设计伙伴。产出设计文档，不写代码
- [Spark](../../.agents/skills/workflow-spark/SKILL.md) ✅ — 头脑风暴 → 设计 spec。逐个问题探索意图，提出 2-3 种方案，写 spec 到 `contexts/thought_review/` 后 STOP，不自动链到实现


### BestPractice（最佳实践）

通用的最佳实践和经验教训。

- [AI 编程核心方法论](../../.agents/skills/bestpractice-ai-programming-mindset/SKILL.md) ✅ — 70%问题、成功标准、可验证性
- [AI 辅助调试诊断](../../.agents/skills/bestpractice-ai-debugging-diagnosis/SKILL.md) ✅ — "代码改不好"的根因诊断决策树
- [AI 产品设计原则](../../.agents/skills/bestpractice-ai-product-design/SKILL.md) ✅ — 线性聊天 vs 知识工作、感知规则解耦
- [多 Agent 并行 analysis](../../.agents/skills/bestpractice-multi-agent-analysis/SKILL.md) ✅ — Topic 分割 50% 重叠、交叉验证

### Guide（指南）

领域实现手册和技术指南。


### Guard（守卫）

安全和约束型守卫 skill。

- [安全守卫](../../.agents/skills/guard-security/SKILL.md) ✅ — Bash、网络、文件写入、敏感输出前的零信任检查

### Analyzer（分析器）

结构化分析和诊断类 skill。

- [结构稳定性分析器](../../.agents/skills/analyzer-structural-stability/SKILL.md) ✅ — 判断一个结构能否长期存活

### Tool（工具）

工具使用方法和最佳路径

- [Semantic Search 工具](../../.agents/skills/tool-semantic-search/SKILL.md) ✅ — 通用语义搜索工具
- [Skill 优化器](../../.agents/skills/tool-skill-optimizer/SKILL.md) ✅ — 诊断并重写 SKILL.md 结构

---

## 如何添加你自己的 Skill

1. skill 存放位置在 `.agents/skills/` 目录
2. 参考现有 skill 文件的格式（元数据、核心说明、使用步骤、示例）
3. 以 `<category>-<name>` 命名目录（例如 `workflow-my-process`、`bestpractice-my-insight`）
4. 分类前缀按能力类型选择，不要随意混用：
   - `workflow-`：分阶段执行流，适合有明确输入、步骤、产出的完整工作流
   - `tool-`：可直接调用的工具能力，适合封装单点能力或操作接口
   - `bestpractice-`：方法论、经验法则、判断原则
   - `guide-`：领域实现指南、技术手册、框架约定
   - `guard-`：安全守卫、约束检查、风险拦截
   - `analyzer-`：分析器、诊断器、评估器
5. 在 INDEX.md 对应分类下添加一行

可以使用 `skill-creator` skill 创建新的 skill，格式参考（最简版）：

```markdown
# Skill: 名称

## When to Use
什么情况下触发这个 skill

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
