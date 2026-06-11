---
name: workflow-llm-wiki
version: 3.0.0
description: |
  LLM Wiki vault 操作手册。

  触发条件：
  - /ingest <path> — 当用户说「ingest」「把这篇文章加入 wiki」「编译到 wiki」「摄取」时触发
  - /query <question> — 当用户说「搜索 wiki」「wiki 中有没有」「查一下 wiki」时触发
  - /lint — 当用户说「检查 wiki」「wiki 健康度」「lint」「有没有断链」时触发
  - /research <topic> — 当用户说「研究一下」「深度调研」「research」时触发
---

# LLM Wiki

**HARD GATE：** 本 skill 只操作 wiki vault（`wiki/` 和 `.llm-wiki/`），以及与本次 wiki 操作直接相关的 `contexts/` 输入材料。
- **不修改** 与当前 wiki 操作无关的 `contexts/` 文件
- **不执行** 与 wiki 无关的 shell 命令
- **不暴露** API key、token、配置中的敏感信息

---

## Operations

- **`/ingest <path>`** — 摄取 `contexts/` 下的材料为 wiki 页面
- **`/query <question>`** — 搜索 wiki 并合成答案
- **`/lint`** — 健康检查：断链、孤岛、矛盾、过时
- **`/research <topic>`** — 联网调研 → 产出 `contexts/survey_sessions/` + ingest

---

## CLI

Wiki vault 的底层操作通过 `philip` CLI 触发（dot notation）：

| 命令 | 说明 |
|---|---|
| `philip wiki.init directory=<dir>` | 初始化 wiki workspace |
| `philip wiki.search query=<text>` | BM25 + ripgrep 搜索（纯文本模式） |
| `philip wiki.search exact_terms='[...]' fuzzy_terms='[...]'` | 结构化搜索（Agent 扩展后的词根） |
| `philip wiki.sync` | 变更检测 + 同步状态更新 |
| `philip wiki.status` | vault 统计和健康摘要 |
| `philip wiki.graph` | wiki 拓扑分析（社区、枢纽、孤岛、缺页） |

---

## Invariants

Before any operation, read these files from `wiki/`:

1. `wiki/wiki-purpose.md` — 范围定义
2. `wiki/wiki-schema.md` — 命名规范、frontmatter 规则
3. `wiki/wiki-agent.md` — Agent 行为规则（单一源，无 CLAUDE.md/AGENTS.md fallback）

`contexts/` 是 wiki 的输入层：`contexts/clippings/`、`contexts/survey_sessions/`、`contexts/thought_review/`、`contexts/daily_records/` 都可以作为 ingest 输入。编辑主要发生在 `wiki/`；只有在需要写入 ingest 元数据或研究产物时才回写对应的 `contexts/` 文件。

After **every** operation — ingest, query, lint, research — append a one-line entry to `wiki/wiki-log.md` and run `philip wiki sync`. Do not skip either step.

---

## Operation Costs

| 操作 | 人工 | Agent | 压缩比 |
|:---|:---|:---|:---|
| `/ingest` (单文件) | ~30min | ~5min | ~6x |
| `/ingest` (10页上下文材料) | ~2h | ~15min | ~8x |
| `/query` | ~30min | ~2min | ~15x |
| `/lint` | ~1h | ~5min | ~12x |
| `/research` | ~4h | ~30min | ~8x |

---

## /ingest <path>

Process new context material into the wiki.

### Phase 0: Pre-check

1. **Incremental guard**: Check if the context document has already been ingested — look for `ingested` in its frontmatter. If `ingested` exists and the file has not been modified since that date, skip and report: "Context unchanged since last ingest, skipping." If modified, proceed (this is a re-ingest).

2. Read `wiki/wiki-purpose.md`, `wiki/wiki-schema.md`, and `wiki/wiki-agent.md` to understand scope, naming, and ingest criteria.

3. **Ingest filter**: Evaluate the context document against the MUST / MAY / NEVER criteria from `wiki-agent.md`.

**STOP.** If filtered out → report "Context filtered: [reason]" → DONE.

### Phase 1: Analyze & Plan

4. Read the context material.

5. Decide whether this ingest needs discussion:
   - Wiki has clear structure + small addition → proceed directly (**跳到 Phase 2**）
   - Would change structure/naming/scope → discuss plan first
   - Wiki is empty → discuss organization rules first, write to `wiki-schema.md`

**STOP。** If discussion needed → present plan → wait for user confirmation → Phase 2.

**逃生舱：** 如果用户说 "直接 ingest" 或 "快速 ingest" → 跳过讨论，直接 Phase 2。

### Phase 2: Execute Ingest

6. Run `philip wiki search` or scan `wiki/` to see existing wiki pages.

7. Analyze the context content and decide:
   - Which new wiki pages to create
   - Which existing pages to update
   - What `[[wikilinks]]` to add

8. Write/update markdown files in `wiki/pages/` with proper frontmatter:
   ```yaml
   ---
   title: Page Title
   description: One-line summary
   tags: []
   contexts: [path-to-context.md]
   created: YYYY-MM-DD
   updated: YYYY-MM-DD
   ---
   ```

   GOOD: 每个页面聚焦单一主题，`contexts` 字段指向输入材料
   BAD:  一个页面塞 3 个不相关主题（模型会创建"大杂烩"页面）
   BAD:  `contexts` 字段留空（违反溯源原则）

9. Add frontmatter to the context document:
   ```yaml
   ---
   ingested: YYYY-MM-DD
   wiki_pages: [list of wiki pages created/updated]
   ---
   ```

### Phase 3: Finalize

10. Append entry to `wiki/wiki-log.md`:
    ```
    YYYY-MM-DD HH:MM | ingest | <context-title> → N pages: page-1, page-2, ...
    ```

11. Run `philip wiki sync`.

12. Report to user:
    ```
    DONE
    Context: <path>
    Pages created: N
    Pages updated: N
    Wikilinks: N
    Wanted pages: N (linked but not yet created)
    ```

### Self-Regulation

- 如果 ingest 过程中连续创建 >20 个页面 → **STOP**，向用户确认是否继续
- 如果单个页面写入失败 → 记录错误，继续处理其他页面，最后汇总报告
- 如果 `philip wiki sync` 失败 → **STOP**，上报：

```
STATUS: BLOCKED
REASON: philip wiki sync failed
ATTEMPTED: [error message]
RECOMMENDATION: Check .llm-wiki/config.toml and network connectivity
```

---

## /query <question>

Search the wiki and synthesize answers.

### Phase 0: Scope Check

1. Read `wiki/wiki-purpose.md` to confirm the question is within the wiki's domain.

**STOP。** If out of scope → report "Question outside wiki scope" → DONE.

### Phase 1: Query Expansion

2. Analyze the user's question. Decompose into structured search terms:

   - **exact_terms**: 实体名、错误码、UUID、函数名、专有名词 — 精确匹配不可丢失的词
   - **fuzzy_terms**: 同义词、口语化描述、概念性表达 — 语义泛化的词

   示例：
   - 用户问："Falcon 那个慢查询报警是怎么处理的？"
   - → `exact_terms: ["Falcon"]`
   - → `fuzzy_terms: ["慢查询", "报警", "slow query", "alert", "排查"]`

   **不要分词，不要拆词。** LLM 是翻译官 + 同义词外挂，输出的是完整词根。

3. 调用搜索：
   ```
   philip wiki.search exact_terms='["Falcon"]' fuzzy_terms='["慢查询","报警","slow query","alert","排查"]'
   ```

   如果问题简单（单一概念），也可以直接用 query：
   ```
   philip wiki.search query=agent memory
   ```

### Phase 2: Filter & Read

4. 对每个 snippet 评估和用户问题的相关度：

   | 判断 | 操作 |
   |------|------|
   | content 跟问题无关 | 直接丢弃，不读原文 |
   | content 相关，信息够用 | 直接用 snippet |
   | content 相关，信息不够 | 读原文补充上下文 |

5. 需要读原文的场景：
   - snippet 被截断，需要更多上下文
   - 需要看 frontmatter（tags、contexts、updated）
   - 需要跟踪 `[[wikilinks]]` 到其他页面

   **不要无脑读所有匹配文件。** 只读 snippet 相关但信息不足的文件。

6. 跟踪 `[[wikilinks]]` 和 `## Related` sections，补充关联知识。

### Phase 3: Synthesize & Calibrate

7. 合成答案：
   - 直接回答用户问题
   - 引用来源（`source: wiki/pages/xxx.md, section: ### xxx`）
   - 标注矛盾或知识缺口

8. 校准：对比原始问题和搜索结果
   - 搜索结果是否覆盖了问题的所有方面？
   - 是否有遗漏的关键信息？
   - 如果有缺口 → 明确标注

### Phase 4: Compound (Conditional)

9. **When to compound** (写回 wiki)：
   - Answer connects 3+ wiki pages not previously documented
   - Answer resolves a contradiction
   - Answer fills a knowledge gap with high-confidence synthesis
   - User explicitly asks to save the answer

   **When NOT to compound**:
   - Simple lookup returning what's already on one page
   - Answer relies heavily on information outside the wiki
   - Synthesis is speculative or low-confidence

   GOOD: 写回一个 synthesis 页面，frontmatter 含 `source_type: query-synthesis`
   BAD:  每次 query 都写回（会产生大量低价值页面）
   BAD:  不写回（知识无法复利）

10. If compounding → create synthesis page → update cross-references → append to log → sync.

### Phase 5: Report

11. Report to user:
    ```
    DONE
    Answer: [synthesized answer]
    Sources:
    - wiki/pages/xxx.md § ### Section Name (exact)
    - wiki/pages/yyy.md § ## Section Name (semantic)
    Compounded: Yes/No (if Yes, list new pages)
    Gaps: [knowledge gaps found]
    ```

---

## /lint

Health-check the wiki for issues.

Variants: `/lint <page>` — Lint a specific page. `/lint --fix` — Auto-fix safe issues.

### Phase 0: Load Schema

1. Read `wiki/wiki-schema.md` for expected structure and conventions.

### Phase 1: Scan & Classify

2. Scan all pages in `wiki/` and the relevant files in `contexts/`.

3. Build link graph — extract all `[[wikilinks]]`.

4. Check three categories:

**Structural Issues:**
- **Broken links**: `[[wikilinks]]` → non-existent pages
- **Orphan pages**: no incoming links
- **Missing frontmatter**: required fields (title, description, tags, contexts, updated)
- **Naming violations**: not following `wiki-schema.md`

**Content Issues:**
- **Contradictions**: conflicting claims across pages
- **Stale content**: `updated` older than context modification dates
- **Unlinked claims**: empty `contexts` in frontmatter

**Context Issues:**
- **Uningested context docs**: files in `contexts/` without `ingested` frontmatter

### Phase 2: Report

5. Present structured report:
   ```
   ## Lint Report — YYYY-MM-DD
   Total pages: N | Context docs: N
   Issues: critical: X, warning: Y, info: Z

   Critical:
   - [[page-a]] → [[nonexistent]] (broken link)

   Warning:
   - [[page-d]] — no incoming links (orphan)

   Info:
   - [[page-g]] — 2 sentences, consider expanding
   ```

**STOP。** If no `--fix` → wait for user decision.

**逃生舱：** 如果用户说 "auto-fix" → 跳过等待，直接 Phase 3。

### Phase 3: Fix (Conditional)

6. Apply safe fixes:

| Issue | Auto-Fix |
|:---|:---|
| Broken link | Remove link or create stub page |
| Missing frontmatter | Add required fields |
| Orphan page | Add links from related pages |
| Stale content | Re-read context doc, update page |
| Duplicate topics | Merge pages, add alias |

7. **Never auto-fix contradictions** — report for human review.

### Phase 4: Finalize

8. Write `.llm-wiki/lint-result.yaml`.

9. Append to `wiki/wiki-log.md`.

10. Run `philip wiki sync` if changes made.

11. Report:
    ```
    DONE / DONE_WITH_CONCERNS
    Fixed: N issues
    Needs review: N issues (list them)
    ```

---

## /research <topic>

Deep-dive investigation beyond existing wiki content. 虽然命令名保留为 `/research`，但产出层一律使用 `survey_sessions` 语义，而不是旧的 `research/` 目录。

### Phase 0: Query First

1. Read `wiki/wiki-purpose.md` — confirm topic is within scope.

2. Run **Query** first — understand what the wiki already knows. Identify gaps.

**STOP。** If wiki already has comprehensive coverage → report findings → DONE.

### Phase 1: Gather Context Materials

3. Define research question and scope.

4. Search for external materials (limit **5–10 items** per session).

5. For each external material, save the raw clipping to `contexts/clippings/` with frontmatter:
   ```yaml
   ---
   title: Context Title
   url: https://original-url
   author: Author Name
   date: YYYY-MM-DD
   retrieved: YYYY-MM-DD
   type: article | paper | documentation | blog
   ---
   ```

   `contexts/clippings/` 只保存外部收藏过来的原始材料，不承载整理后的调研结论。

### Phase 2: Ingest & Synthesize

6. For each new context material, run the **Ingest** procedure (Phase 0-3).

7. After all context materials are ingested, write the survey session to `contexts/survey_sessions/`:
   ```
   ## Survey Session: [Topic]

   ### Question
   [Original research question]

   ### Findings
   [Synthesized answer]

   ### Context Materials Added
   - contexts/clippings/path.md — what it contributed

   ### Wiki Pages Created/Updated
   - [[page-1]] — what was added

   ### Remaining Gaps
   - What still couldn't be answered
   ```

### Phase 3: Finalize

8. Append to `wiki/wiki-log.md`.

9. Run `philip wiki sync`.

10. Report:
    ```
    DONE
    Context materials added: N
    Pages created: N
    Pages updated: N
    Gaps: [list]
    ```

### Self-Regulation

- 如果本次调研超过 10 个材料 → **STOP**，向用户确认是否继续
- 如果连续 3 个材料都没有产生新页面 → **STOP**，报告"信息密度低，建议缩小范围"

---

## Completion Protocol

- **DONE** — 全部步骤完成，输出已验证
- **DONE_WITH_CONCERNS** — 完成但有待确认事项（如 wanted pages、knowledge gaps）
- **BLOCKED** — 无法继续（如 sync 失败、权限不足），说明原因和已尝试的方法
- **NEEDS_CONTEXT** — 缺少必要信息（如 wiki-agent.md 缺失），明确列出需要什么

上报格式：
```
STATUS: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
REASON: [1-2 句话]
DETAILS: [具体信息]
RECOMMENDATION: [下一步建议]
```

---

**Skill Version**: 3.0.0
**Author**: Meta42
**Status**: Active & Enforced
**Last Updated**: 2026-06-11
