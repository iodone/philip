# LLM Wiki 轻量级双路搜索架构设计文档

## 0. 设计哲学 (Philosophy)
- **如无必要，勿增实体**：不引入任何 Vector DB 或持久化全文索引。对于个人 Wiki（千篇文档量级），直接走「运行时内存计算（In-Memory On-The-Fly）」，查询结束后索引即销毁。
- **大模型能力下放**：抛弃同义词词典，通过 Agent 的 Zero-Shot Query Expansion 实现语义泛化，将模糊意图转化为结构化的检索词根。
- **结构先于文本**：切片粒度对齐 Markdown 标题边界，上下文必须携带强元数据（文件路径 + 标题 + 行号范围）。

## 1. 核心架构拓扑 (Pipeline)

```
用户查询
   │
   ▼
┌─────────────────────────────────┐
│ 1. Query Expansion (Skill 层)    │  Agent 将模糊查询扩展为结构化词根
│    输入: "Falcon 那个卡住的图表"    │
│    输出: exact_terms + fuzzy_terms │
└──────────┬──────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────────────┐
│ 2a. Grep │ │ 2b. BM25         │
│ exact_   │ │ exact_terms      │
│ terms    │ │ + fuzzy_terms    │
│ 原样正则  │ │ → jieba 分词 →    │
│ 不分词    │ │ 倒排索引打分       │
└────┬─────┘ └────┬─────────────┘
     │            │
     └─────┬──────┘
           ▼
┌─────────────────────────────────┐
│ 3. 梯队排序 (Tiered Ranking)     │
│    Tier 1 (VIP): grep 命中 +     │
│      包含 exact_terms → 置顶     │
│    Tier 2: BM25 高分 → 次优先    │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│ 4. 上下文组装 (Context Assembly)  │
│    带 source / section / lines /  │
│    type / content 的结构化 snippet│
└─────────────────────────────────┘
```

## 2. 术语定义

| 术语 | 定义 |
|------|------|
| **Block** | 以 Markdown 标题（`#`~`######`）为边界划分的独立逻辑块。是索引和搜索的最小单元。 |
| **Chunk** | 等同于 Block。当前实现不做二次切分。 |
| **exact_terms** | Agent 扩展出的精确词根（实体名、错误码、UUID、函数名）。送给 ripgrep 原样匹配，**绝不分词**。 |
| **fuzzy_terms** | Agent 扩展出的语义词根（同义词、口语化描述）。和 exact_terms 一起经 jieba 分词后送给 BM25。 |

## 3. 切片策略 (Block Splitting)

在 Search 阶段动态切块（不构建持久化索引）：

- **切分规则**：以 Markdown 标题行（`# ~ ######`）为边界
- **Block 元数据**：`{ file_path, slug, header, content, line_start, line_end }`
- **超大 Block**：当前不做二次切分。大部分 wiki section 在 200-500 token 内，极端情况（如长代码块）作为一个 Block 进 BM25，可能影响打分精度，但可接受。

```python
# parse_blocks 示例
"# Agent 边界设计\n\n六种边界框架...\n\n## 上下文边界\n\n..." →
  Block(header="# Agent 边界设计", content="...", line_start=1, line_end=8)
  Block(header="## 上下文边界", content="...", line_start=9, line_end=20)
```

## 4. 分词策略 (Tokenization)

统一使用 **jieba** 分词，保证索引端和查询端 token 空间一致。

| 场景 | 分词？ | 说明 |
|------|--------|------|
| BM25 索引构建（文档端） | ✅ jieba | Block 内容过 jieba 切成 token，建倒排索引 |
| BM25 查询（查询端） | ✅ jieba | `exact_terms + fuzzy_terms` 拼接后过 jieba 切碎 |
| ripgrep 查询 | ❌ 不分词 | `exact_terms` 原样拼正则，连空格都不动 |

```python
# jieba 分词
import jieba
jieba.lcut("慢查询报警") → ["慢查询", "报警"]       # 语义分词
jieba.lcut("store_sales_dod_rate") → ["store_sales_dod_rate"]  # 英文不切

# 对比旧方案（unigram + bigram）
"慢查询" → ["慢", "查", "询", "慢查", "查询"]       # 噪声多
```

## 5. 检索双引擎设计 (Retrieval Engines)

### 5.1 Query Expansion（Skill 层，非代码层）

在调用 `wiki.search` 前，Agent 必须先执行查询重写。这是 **workflow-llm-wiki skill** 的规则，不是 search 代码的逻辑。

- **输入**："Falcon 的慢查询报警"
- **输出**：
  ```json
  {
    "exact_terms": ["Falcon", "store_sales_dod_rate"],
    "fuzzy_terms": ["慢查询", "slow query", "报警", "alert", "P1"]
  }
  ```

wiki.search 支持两种输入：
- `query=machine learning` — 纯文本，向后兼容，内部等价于 `exact_terms + fuzzy_terms`
- `exact_terms='[...]' fuzzy_terms='[...]'` — 结构化输入，Agent 扩展后的词根

### 5.2 引擎 A：Ripgrep 精确打击

- **职责**：确保强实体绝对不漏
- **输入**：`exact_terms`（原样，不分词）
- **实现**：`ripgrepy` 执行正则 `Falcon|store_sales_dod_rate`
- **返回**：`{file_path: [line_numbers]}`，映射回 Block（通过 `line_start <= line_no <= line_end`）

### 5.3 引擎 B：In-Memory BM25

- **职责**：语义兜底，处理口语化描述和概念性查询
- **输入**：`exact_terms + fuzzerms` 拼接后经 jieba 分词
- **实现**：运行时对所有 Block 建倒排索引（`df`, `tf`, `doc_lengths`），查询后销毁
- **无 mmap**：BM25 用 Python dict 存倒排索引，不是连续内存数组，mmap 不适用

## 6. 排序规则 (Tiered Ranking)

- **Tier 1 (VIP)**：grep 命中**且** Block 内容包含 exact_terms → 强制置顶
- **Tier 2**：BM25 高分（fuzzy_terms 语义匹配）
- grep-only 命中（不在 BM25 结果中但包含 exact_terms）也归入 Tier 1

## 7. 上下文组装 (Context Assembly)

```json
{
  "mode": "tiered",
  "exact_terms": ["Falcon"],
  "fuzzy_terms": ["慢查询", "报警"],
  "snippets": [
    {
      "source": "wiki/pages/falcon-tuning.md",
      "section": "### 慢查询排查",
      "lines": [45, 60],
      "type": "exact",
      "content": "如果发现 OLAP 层的计算延迟..."
    },
    {
      "source": "wiki/pages/monitoring.md",
      "section": "## 报警体系",
      "lines": [12, 25],
      "type": "semantic",
      "content": "P1 报警的处理流程..."
    }
  ]
}
```

## 8. 依赖

| 依赖 | 用途 |
|------|------|
| `jieba` | 中文分词（BM25 索引 + 查询） |
| `ripgrepy` | ripgrep Python SDK（精确匹配） |
| `ripgrep` (rg) | 系统命令，ripgrepy 的底层依赖 |
