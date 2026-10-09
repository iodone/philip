# CLI Capabilities — Wiki

Wiki 是 Philip 的知识库管理能力，提供 workspace 初始化、BM25 + ripgrep 搜索、链接图分析和变更同步。

## 初始化

```bash
philip wiki.init directory=/path/to/workspace
```

创建完整 workspace 结构：

```
/path/to/workspace/
├── AGENTS.md               # Agent session 入口协议
├── README.md               # Workspace 总览
├── rules/
│   ├── SOUL.md             # Agent 身份定义
│   ├── USER.md             # 用户偏好与原则
│   ├── COMMUNICATION.md    # 协作方式
│   ├── SECURITY.md         # 安全规则
│   ├── WORKSPACE.md        # 目录路由速查
│   ├── axioms/             # 稳定判断规则
│   └── skills/             # Skill 索引
├── .agents/skills/
│   └── workflow-llm-wiki/SKILL.md  # 内置 wiki 操作 skill
├── contexts/               # 输入层（ingest 材料）
│   ├── blog/               # 博客草稿
│   ├── clippings/          # 外部原始资料
│   ├── daily_records/      # 日级记录
│   ├── life_record/        # 生活观察
│   ├── survey_sessions/    # 调研过程
│   └── thought_review/     # 深度分析
├── wiki/
│   ├── pages/              # Wiki 页面（Obsidian 兼容）
│   ├── wiki-purpose.md     # Wiki 目的与范围
│   ├── wiki-schema.md      # 页面规范
│   ├── wiki-agent.md       # Agent 行为规则
│   └── wiki-log.md         # 操作日志
└── .llm-wiki/
    └── config.toml         # Vault 配置
```

### 选项

| 选项 | 说明 |
|:---|:---|
| `force=true` | 覆盖已有文件和 skill |

重复运行安全：已有文件默认跳过。

## 搜索

```bash
philip wiki.search query=<query>
philip wiki.search query=<query> limit=20         # 更多结果
philip wiki.search exact_terms='["Falcon"]' fuzzy_terms='["慢查询","报警"]'   # 结构化输入：精确词 + 语义词
```

BM25（jieba 分词，支持 CJK）负责语义召回，ripgrep 负责精确匹配（`exact_terms` 原样拼正则）；两者按 tiered ranking 融合，精确命中优先。搜索为运行时内存计算，无外部索引或数据库依赖。

## 同步

```bash
philip wiki.sync
philip wiki.sync dry_run=true   # 仅展示变更，不更新状态
```

基于 mtime + SHA-256 内容哈希检测变更（added/modified/deleted），更新本地同步状态。

## 图分析

```bash
philip wiki.graph
```

分析 wiki 页面间的 `[[wikilinks]]` 关系：
- 社区发现（label propagation）
- Hub 页（高连接度）
- Orphan 页（无入链）
- Wanted 页（被引用但未创建）

## 状态

```bash
philip wiki.status
```

输出 wiki 健康概览：页面数、contexts 数、链接数、最近修改、健康问题。

## 配置参考

### Vault 配置（`.llm-wiki/config.toml`）

| 配置项 | 说明 | 默认值 |
|:---|:---|:---|
| `vault.name` | Wiki 名称 | `My Wiki` |
| `vault.language` | 语言 | `en` |
| `vault.context_dir` | 输入目录名 | `contexts` |
| `vault.wiki_dir` | Wiki 目录名 | `wiki` |
| `vault.pages_subdir` | 页面子目录名 | `pages` |
