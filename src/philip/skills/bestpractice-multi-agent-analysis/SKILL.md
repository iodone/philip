---
name: bestpractice-multi-agent-analysis
description: 文档分析、调研任务、复杂信息整合
---


# 多 Agent 并行分析最佳实践

## 元数据

- **类型**: BestPractice
- **适用场景**: 文档分析、调研任务、复杂信息整合
- **创建日期**: 2026-02-21
- **来源**: 2026-02-16 "4+4"多 Agent 文档分析实验

---

## 实验背景

对房产调研文档进行并行分析，采用"4 个综合 + 4 个专题 + 1 个交叉验证"的 9 Agent 架构。

最终产出：11 个分析 JSON（4108 行）及可视化网站。

---

## 核心发现
### Multi-agent 的真正价值：上下文窗口隔离

Multi-agent 框架的真正价值不在于角色扮演（PM/Dev/QA 分工），而在于**上下文窗口隔离**。

- 管理 Agent 不需要知道语法错误等低层细节，只需高层规划
- 每个 Agent 专注自己的抽象层次，减少信息过载
- 盲目模仿人类协作模式（如机械分工 PM/Dev/QA）是错误的 AI-native 设计

### Topic 分割保持 50% 重叠

不要把任务完全切分，而是让相邻 Agent 有 50% 的职责重叠。

原因：
- 交叉区域最容易遗漏
- 重叠允许交叉验证
- 不同 Agent 对同一内容可能发现不同角度

### 交叉验证发现不一致

实验中发现的关键不一致：
- 车库转换可行性评估矛盾（Agent A 认为可行，Agent B 指出法规限制）
- 750 平方英尺阈值在不同文档中的解释差异

不一致不是 Bug，是特性——它暴露了信息中的矛盾和模糊点。

### 专题深入发现跨维度洞察

专题 Agent 比综合 Agent 更容易发现：
- 跨文档的模式
- 数值阈值（如 750 平方英尺）
- 隐藏的约束条件

---

## 推荐架构

### 小型任务（≤3 个文档）

```
2-3 个综合 Agent（50% 重叠）
```

### 中型任务（3-10 个文档）

```
3-4 个综合 Agent + 2-3 个专题 Agent
```

### 大型任务（>10 个文档）

```
4 个综合 Agent + 4 个专题 Agent + 1 个交叉验证 Agent
```

### Agent 分工示例

| 类型 | 数量 | 职责 |
|------|------|------|
| 综合 | 4 | 各自覆盖完整文档集，50% 重叠 |
| 专题 | 4 | 分别关注：财务/法规/技术/市场 |
| 交叉验证 | 1 | 比对前 8 个 Agent 的输出，标记不一致 |

---

## 输出格式

推荐使用结构化 JSON：

```json
{
  "agent_id": "comprehensive_1",
  "scope": ["doc1.md", "doc2.md", "doc3.md"],
  "findings": [
    {
      "topic": "主题",
      "summary": "摘要",
      "evidence": "引用原文",
      "confidence": "high/medium/low"
    }
  ],
  "cross_refs": ["与 comprehensive_2 的发现 X 相关"]
}
```

---

## 与其他 Skill 的关系

本 bestpractice 是 [并行 Subagent 工作流](../workflow-parallel-subagents/SKILL.md) 的**案例与扩展**：workflow 定义何时用、核心参数、执行流程；本文档提供「4+4」实验的方法论总结与输出格式。

- 配合 `workflow-parallel-subagents` 的并行执行框架
- 配合 `workflow-deep-research-survey` 的调研工作流
- 输出可用于 `bestpractice-staged-approach` 的 Stage 2 处理

## 变更日志
| 日期 | 变更 |
|------|------|
| 2026-02-22 | 补充核心发现：上下文窗口隔离是 Multi-agent 真正价值 |
| 2026-02-21 | 初始版本，来自 2026-02-16 实验总结 |
