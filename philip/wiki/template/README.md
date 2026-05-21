# Workspace

A knowledge workspace managed by [Philip](https://github.com/iodone/philip) and its AI agents.

## Structure

```
├── AGENTS.md               # Agent session entry protocol
├── README.md               # This file
├── rules/                  # Agent identity & operating rules
│   ├── SOUL.md             # Agent identity
│   ├── USER.md             # User preferences & principles
│   ├── COMMUNICATION.md    # Collaboration style
│   ├── SECURITY.md         # Safety boundaries
│   ├── WORKSPACE.md        # Directory routing reference
│   ├── axioms/             # Stable judgment rules
│   └── skills/             # Skill index & classification
├── .agents/skills/         # Executable skill files
├── contexts/               # Input layer for wiki ingest
│   ├── blog/               # Blog drafts & long-form material
│   ├── clippings/          # External raw materials
│   ├── daily_records/      # Daily timeline logs
│   ├── life_record/        # Life experiences & observations
│   ├── survey_sessions/    # Research session outputs
│   └── thought_review/     # Deep analysis & retrospectives
└── wiki/                   # Stable knowledge base
    ├── pages/              # Wiki pages (Obsidian-compatible)
    ├── wiki-agent.md       # Wiki agent behavior rules
    ├── wiki-purpose.md     # Wiki scope & purpose
    ├── wiki-schema.md      # Page naming & frontmatter rules
    └── wiki-log.md         # Wiki change log
```

## Usage

```bash
# Search wiki
philip wiki search <query>

# View graph analysis
philip wiki graph

# Sync changes
philip wiki sync
```
