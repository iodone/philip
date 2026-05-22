---
name: tool-semantic-search
description: 需要对某个主题进行深度、全面、可验证的第三方调研
---

# 语义搜索技能 (Semantic Search Skill)
## 1. 技能概览

`semantic-search` 是一个**通用语义搜索工具**，可对任意本地文本文件建索引并做自然语言查询。它超越关键词匹配，理解语义层面的关联，适用于任何需要从大量文本中按意义而非字面检索内容的场景。

最典型的使用场景是搜索用户的个人知识库（博客、日志、调研报告），但工具本身不限于此。`--file-list` 可以指向任何文本文件集合：聊天记录、第三方文档、调研素材、代码注释等。

**对于用户的知识库，这是获取深层偏好和个人哲学的核心工具，是实现 AI Heartbeat Step 2 (Reflection Layer) 的关键基础设施。**

### 1.1 何时使用

**场景 A：搜索用户的知识库（最常见）**
 **深度背景挖掘**：了解用户在某个话题（如 "Agentic AI"、"天文摄影"）上的长期观点演变。
 **关联思考**：寻找与当前任务相关的历史实验、随笔或反思，即使关键词不完全匹配。
 **决策支持**：调取过去的复盘或设计讨论，为当前架构决策提供参考。
 **消除歧义**：当用户提到一个模糊的概念时，找到最相关的历史定义。
 **构建 Axiom / Digital Twin**：沉淀公理或深度反思时，**必须**先执行语义搜索以对齐历史认知。

**场景 B：分析任意文本集合**
 **第三方内容分析**：在聊天记录、访谈转录、会议纪要中按主题检索（如"找出某人关于 AI 的所有讨论"）。
 **调研素材挖掘**：在一批下载的文档/报告中做语义检索，找到关键词搜不到的相关段落。
 **认知画像提取**：从大量对话数据中按维度（技术观点、价值观、方法论）提取模式。
 **跨文档主题发现**：在异构文本集合中发现语义相关但措辞不同的内容。

### 1.2 触发建议

**主动触发（务必执行）**：
 当你在构建 `rules/axioms/` 下的公理文档时
 当任务涉及用户的核心价值观、方法论或哲学体系时
 当你需要理解用户在某个领域的"思想演变史"时
 当你在做反思层工作（沉淀公理、深度复盘）时
 当你需要从大量文本中按主题或语义维度提取信息时（不限于用户的内容）

**被动触发（用户明确要求）**：
 "搜一下我之前对 X 的看法"
 "找找看有没有相关的背景资料"
 "帮我总结一下在 Y 这个话题上的思考"
 "我以前是怎么解决类似问题的？"
 "在这批聊天记录/文档里找 X 相关的内容"
 "分析某人在 Y 话题上的观点"

---

## 2. 使用说明

### 2.1 核心命令
```bash
python tools/semantic_search/main.py \
    --file-list tmp/search_files.txt \
    --query "<自然语言查询语句>" \
    --top-k 10 \
    --cache-dir .knowledge_cache
```

### 2.2 参数规范
- `--file-list`：必需。指向一个包含待搜索文件路径列表的文本文件。建议放在 `tmp/` 目录下。
- `--query`：必需。完整的、描述性的句子。例如 "用户对 Agentic AI 核心矛盾的最新思考" 优于 "Agentic AI"。
- `--top-k`：可选。返回的相关片段数量，默认 5，建议设为 10 以获得更广的上下文。
- `--cache-dir`：**务必指定为 `.knowledge_cache`**（根目录下），以复用预计算好的特征向量，大幅提升响应速度。

---

## 3. 标准工作流

1.  **准备文件列表**：根据需求筛选知识库区域（参考 `rules/WORKSPACE.md`）。
    ```bash
    mkdir -p tmp
    # 示例：搜索博客和调研报告
    find contexts/blog/content contexts/survey_sessions -name "*.md" > tmp/search_files.txt
    ```
2.  **执行语义搜索**：
    ```bash
    source .venv/bin/activate
    export OPENAI_API_KEY=$(grep OPENAI_API_KEY .env | cut -d '=' -f2)
    python tools/semantic_search/main.py --file-list tmp/search_files.txt --query "..." --top-k 10 --cache-dir .knowledge_cache
    ```
3.  **分析与综合**：阅读搜索结果（通常包含 score, source_file, text），结合元数据（日期、分类）进行综合分析。
4.  **清理**：任务完成后删除 `tmp/search_files.txt`。

---

## 4. 常用搜索路径

搜索用户的知识库时，优先考虑以下路径：
- `contexts/blog/content/`：深度技术文章与核心思考。
- `contexts/daily_records/`：每日日志，记录了最真实的想法演变。
- `contexts/survey_sessions/`：深度调研结论。
- `contexts/life_record/data/`：生活录音转录（含每日生活摘要和会议记录）。
  - 2026年数据：`contexts/life_record/data/<YYYYMMDD>/`
  - 2025年数据：`contexts/life_record/data/2025/<YYYYMMDD>/`
  - 每日摘要 `.md` 和原始 transcript `.csv` 都可搜索
- `rules/skills/INDEX.md`：方法论沉淀。

以上是常用快捷路径。`--file-list` 可以指向任何文本文件集合，例如：
```bash
# 搜索生活转录（含2025和2026）
find contexts/life_record/data -name "*.md" -not -path "*/.venv/*" > tmp/search_files.txt

# 搜索微信聊天记录
find contexts/wechat -name "*.csv" > tmp/search_files.txt

# 搜索某个调研项目的所有素材
find contexts/<your-project> -name "*.md" > tmp/search_files.txt

# 搜索任意临时文档
ls adhoc_jobs/some_project/*.txt > tmp/search_files.txt
```

---
**版本**: 1.2.0
**最后更新**: 2026-03-15
