---
name: workflow-parallel-subagents
description: 调用后台 agent、并行执行多个独立子任务
---

# 并行 Subagent 工作流

## 元数据

- **类型**: Workflow
- **适用场景**: 调用后台 agent、并行执行多个独立子任务
- **创建日期**: 2026-02-20
- **最后更新**: 2026-03-01

---

## 何时使用并行模式

满足以下全部条件时，才值得并行：

1. **任务可拆分**：能分解为至少 2 个相对独立的子任务
2. **子任务有规模**：每个子任务预期需要 ≥5 个 tool call 才能完成
3. **子任务有价值**：并行执行比串行执行能显著节省时间

不满足时，直接串行执行，不要为了并行而并行。

---

## 并行执行流程

### 1. 评估与分割

识别 3-5 个关键维度后，根据任务类型确定 overlap：

| 任务类型 | Overlap 范围 | 原因 |
|---------|-------------|------|
| 调研/创造性任务 | 30% - 50% | 交叉验证、查漏补缺 |
| 代码/执行任务 | 0% - 20% | 效率优先，减少重复 |

### 2. 并行启动

在同一条消息中发出所有调用。使用 `mcp_task()` 根据任务类型选择 category 或 subagent_type：

```python
# 调研/分析任务 → 使用 subagent_type
mcp_task(
    subagent_type="explore",
    run_in_background=True,
    prompt="具体维度描述..."
)

# 实现任务 → 使用 category 委派
mcp_task(
    category="deep",
    load_skills=["git-master"],
    run_in_background=True,
    prompt="具体实现要求..."
)
```

每个 subagent 的 prompt 应包含：
- 具体负责的维度/范围
- 预期的 overlap 区域（让 agent 知道其他人也在看这部分）
- 输出格式要求

### 3. 等待与整合

启动后什么都不做，等系统通知。系统会在 subagent 完成时自动推送 `<system-reminder>` 通知。收到通知后，用 `mcp_background_output(task_id="...")` 取回结果，然后交叉验证重叠区域的信息并合成最终输出。

**⚠️ 关于 `background_output` 的常见误解：**

`background_output` 的 `block` 和 `timeout` 参数**不会**让调用阻塞等待任务完成。无论你设置 `timeout=120` 还是 `timeout=600`，它都是**立即返回当前已有的输出**。这意味着：

- **错误做法**：反复调用 `background_output(block=true, timeout=600)` 试图"等"任务完成——每次都会立即返回相同的部分结果，造成无意义的 polling。
- **正确做法**：发出 background task 后，**结束当前回复**（end your response），等待系统推送的 `<system-reminder>` 通知，收到后再调用 `background_output` 一次性取回完整结果。

简而言之：`background_output` 是**取结果**的工具，不是**等结果**的工具。等待由系统通知机制完成。

---

## 示例

### 调研任务（30-50% overlap）

```
调研「某技术框架的采用情况」
├─ Agent 1（explore）：核心特性 + 社区活跃度
├─ Agent 2（librarian）：社区活跃度 + 企业案例
├─ Agent 3（oracle）：企业案例 + 竞品对比
└─ Overlap：社区和企业案例都有覆盖，可交叉验证
```

### 代码任务（0-20% overlap）

```
实现「用户认证系统」
├─ Task 1：认证核心逻辑 + Token 管理
├─ Task 2：数据库模型 + 迁移脚本
├─ Task 3：API 端点 + 测试用例
└─ Overlap：接口定义处有少量重叠，确保对接正确
```

---

## 注意事项

- **不要过度并行**：2-3 个精心设计的 subagent 通常优于 5 个松散的
- **prompt 质量**：subagent 的 prompt 要足够具体，否则结果会很浅
- **成本意识**：并行会消耗更多 token，评估是否值得
- **中间结果**：通常不需要保存，只在主 agent 中整合
