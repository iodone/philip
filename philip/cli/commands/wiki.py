"""Philip wiki commands — full Python implementation of llm-wiki CLI."""

from __future__ import annotations

from pathlib import Path

import click

from philip.wiki.config import (
    VaultSection,
    WikiConfig,
    find_vault_root,
    load_config,
    load_template,
    require_vault_root,
    vault_paths,
)
from philip.wiki.graph import analyze_graph
from philip.wiki.search import bm25_search, rrf_merge
from philip.wiki.skills import install_skills_to, list_skills
from philip.wiki.sync import compute_sync, load_sync_state, save_sync_state, update_sync_state
from philip.wiki.wiki import list_markdown_files, load_wiki_pages


@click.group()
def wiki() -> None:
    """Wiki vault operations (full Python implementation)."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@wiki.command()
@click.argument("directory", default=".")
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def init(directory: str, force: bool) -> None:
    """Initialize a new wiki workspace.

    Creates the full workspace structure including wiki vault, rules,
    contexts, and agent skills. Existing files are skipped unless
    --force is used to overwrite. Safe to run multiple times —
    each run fills in missing pieces.
    """
    target = Path(directory).resolve()

    default_config = WikiConfig(
        vault=VaultSection(name="My Wiki", language="en", wiki_dir="wiki", pages_subdir="pages")
    )
    paths = vault_paths(target, default_config)

    # --- Create directories ---
    dirs_to_create = [
        paths.wiki,             # wiki/pages/
        paths.contexts,         # contexts/
        paths.contexts / "blog",
        paths.contexts / "clippings",
        paths.contexts / "daily_records",
        paths.contexts / "life_record",
        paths.contexts / "survey_sessions",
        paths.contexts / "thought_review",
        paths.rules_dir,        # rules/
        paths.rules_dir / "axioms",
        paths.rules_dir / "skills",
        paths.agents_skills_dir,  # .agents/skills/
        paths.llm_wiki_dir,     # .llm-wiki/
    ]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)

    # --- Create files ---
    files_to_create = [
        # Wiki templates
        (paths.purpose, load_template("purpose")),
        (paths.schema, load_template("schema")),
        (paths.agent, load_template("agent")),
        (paths.config, load_template("config")),
        (paths.log, load_template("log")),
        # Workspace-level files
        (target / "AGENTS.md", load_template("agents_md")),
        (target / "README.md", load_template("readme_md")),
        # Rules stubs
        (paths.rules_dir / "SOUL.md", load_template("rules_soul")),
        (paths.rules_dir / "USER.md", load_template("rules_user")),
        (paths.rules_dir / "COMMUNICATION.md", load_template("rules_communication")),
        (paths.rules_dir / "SECURITY.md", load_template("rules_security")),
        (paths.rules_dir / "WORKSPACE.md", load_template("rules_workspace")),
    ]

    created_files: list[str] = []
    skipped_files: list[str] = []
    for path, content in files_to_create:
        if not path.exists() or force:
            path.write_text(content, encoding="utf-8")
            created_files.append(str(path.relative_to(target)))
        else:
            skipped_files.append(str(path.relative_to(target)))

    # --- Install built-in skills to workspace ---
    skill_result = install_skills_to(paths.agents_skills_dir, overwrite=force)
    skill_installed = [f".agents/skills/{name}/SKILL.md" for name in skill_result.installed]
    skill_skipped = [f".agents/skills/{name}/SKILL.md" for name in skill_result.skipped]
    if not force:
        created_files.extend(skill_installed)
        skipped_files.extend(skill_skipped)
    elif skill_installed:
        created_files.extend(skill_installed)

    click.echo(f"Initialized wiki workspace in {target}")
    click.echo("")
    if created_files:
        click.echo("Created:")
        for f in created_files:
            click.echo(f"  {f}")
    if skipped_files and not force:
        click.echo("Skipped (already exists):")
        for f in skipped_files:
            click.echo(f"  {f}")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Edit wiki/wiki-purpose.md to describe your wiki")
    click.echo("  2. Edit rules/SOUL.md to define agent identity")
    click.echo("  3. Add wiki pages to wiki/pages/")
    click.echo("  4. Use `philip wiki search <query>` to find content")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@wiki.command()
@click.argument("query")
@click.option("-n", "--limit", default=10, help="Max results.")
@click.option("--bm25-only", is_flag=True, help="Force BM25-only search.")
def search(query: str, limit: int, bm25_only: bool) -> None:
    """Search wiki pages (BM25 + vector search if configured)."""
    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)
    pages = load_wiki_pages(paths.wiki)

    if not pages:
        click.echo("No wiki pages found. Use `philip wiki init` to add content.")
        return

    pages_by_slug = {p.slug: p for p in pages}

    # BM25 search (get 2x candidates for potential RRF merge)
    bm25_results = bm25_search(pages, query, limit * 2)

    # Try vector search if DB9 configured
    vector_results: list[dict[str, float]] = []
    hybrid_mode = False

    if not bm25_only and config.db9 and config.db9.url:
        try:
            from philip.wiki.db9 import create_db9_client

            db9 = create_db9_client(config)
            if db9:
                db_results = db9.vector_search(query, limit * 2)
                vector_results = [{"slug": r["slug"], "score": r["similarity"]} for r in db_results]
                hybrid_mode = len(vector_results) > 0
                db9.close()
        except Exception as err:
            click.echo(f"DB9 search failed, falling back to BM25: {err}", err=True)

    if hybrid_mode:
        final_results = rrf_merge(
            [{"slug": r.page.slug, "score": r.score} for r in bm25_results],
            vector_results,
            limit,
        )
        click.echo(f'Results for "{query}" (hybrid BM25 + vector, {len(final_results)} matches):\n')
    else:
        final_results = [{"slug": r.page.slug, "score": r.score} for r in bm25_results[:limit]]
        click.echo(f'Results for "{query}" (BM25, {len(final_results)} matches):\n')

    if not final_results:
        click.echo(f'No results for "{query}"')
        return

    for r in final_results:
        slug = r["slug"]
        score = r["score"]
        click.echo(f"  {slug}")
        page = pages_by_slug.get(slug)
        if page:
            click.echo(f"    Title: {page.title}")
            if page.description:
                click.echo(f"    {page.description}")
            click.echo(f"    Score: {score:.4f} | Tags: {', '.join(page.tags) or 'none'}")
        click.echo("")


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------


@wiki.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def graph(as_json: bool) -> None:
    """Analyze wiki link graph — communities, hubs, orphans, wanted pages."""
    import json

    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)
    pages = load_wiki_pages(paths.wiki)

    if not pages:
        click.echo("No wiki pages found.")
        return

    analysis = analyze_graph(pages)

    if as_json:
        data = {
            "nodes": len(analysis.nodes),
            "edges": len(analysis.edges),
            "orphans": analysis.orphans,
            "wantedPages": analysis.wanted_pages,
            "communities": analysis.communities,
            "hubs": [
                {"slug": h.slug, "connections": h.link_count + h.incoming_count}
                for h in analysis.hubs
            ],
        }
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    click.echo(f"Graph Analysis: {len(analysis.nodes)} pages, {len(analysis.edges)} links\n")

    if analysis.hubs:
        click.echo("Top Hub Pages:")
        for hub in analysis.hubs[:5]:
            click.echo(f"  [[{hub.slug}]] — {hub.link_count} outgoing, {hub.incoming_count} incoming")
        click.echo("")

    if analysis.communities:
        click.echo(f"Communities ({len(analysis.communities)} detected):")
        for i, (_, members) in enumerate(analysis.communities.items(), 1):
            click.echo(f"  Cluster {i}: {', '.join(members)}")
        click.echo("")

    if analysis.orphans:
        click.echo(f"Orphan Pages ({len(analysis.orphans)}, no incoming links):")
        for orphan in analysis.orphans:
            click.echo(f"  [[{orphan}]]")
        click.echo("")

    if analysis.wanted_pages:
        click.echo(f"Wanted Pages ({len(analysis.wanted_pages)}, linked but not created):")
        for page_name, linked_from in analysis.wanted_pages.items():
            click.echo(f"  [[{page_name}]] — linked from {len(linked_from)} page(s)")
        click.echo("")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@wiki.command()
def status() -> None:
    """Show wiki statistics and health summary."""
    import re
    from datetime import date

    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)

    pages = load_wiki_pages(paths.wiki)
    context_files = list_markdown_files(paths.contexts)
    sync_state = load_sync_state(paths.sync_state)

    # Count log entries
    log_entries = 0
    if paths.log.exists():
        log_content = paths.log.read_text(encoding="utf-8")
        log_entries = len(re.findall(r"^## \[", log_content, re.MULTILINE))

    # Health checks
    issues: list[str] = []
    legacy_renames = [
        ("purpose.md", "wiki-purpose.md"),
        ("schema.md", "wiki-schema.md"),
        ("log.md", "wiki-log.md"),
    ]
    for old_name, new_name in legacy_renames:
        if not (root / new_name).exists() and (root / old_name).exists():
            issues.append(f"legacy {old_name} detected — rename to {new_name} (v0.4.2 vault file rename)")

    if not paths.purpose.exists():
        issues.append("wiki-purpose.md missing")
    if not paths.schema.exists():
        issues.append("wiki-schema.md missing")

    pages_without_contexts = [p for p in pages if not p.contexts]
    if pages_without_contexts:
        issues.append(f"{len(pages_without_contexts)} pages without contexts")

    # Broken wikilinks
    slug_set = {p.slug.lower() for p in pages}
    broken_links = 0
    for page in pages:
        for link in page.wikilinks:
            if link.lower().removesuffix(".md") not in slug_set:
                broken_links += 1
    if broken_links:
        issues.append(f"{broken_links} broken wikilinks")

    # Recent pages
    recent_pages = sorted(pages, key=lambda p: p.mtime, reverse=True)[:5]

    # Output
    click.echo(f"Wiki: {config.vault.name}")
    click.echo(f"Language: {config.vault.language}")
    click.echo("")
    click.echo(f"Pages:    {len(pages)}")
    click.echo(f"Contexts: {len(context_files)}")
    click.echo(f"Links:   {sum(len(p.wikilinks) for p in pages)}")
    click.echo(f"Log:     {log_entries} entries")
    if sync_state.last_sync:
        click.echo(f"Synced:  {sync_state.last_sync}")
    click.echo("")

    if recent_pages:
        click.echo("Recently Modified:")
        for page in recent_pages:
            d = date.fromtimestamp(page.mtime / 1000).isoformat()
            click.echo(f"  {d} — [[{page.slug}]]")
        click.echo("")

    if issues:
        click.echo("Health Issues:")
        for issue in issues:
            click.echo(f"  ⚠ {issue}")
        click.echo("")
        click.echo("Run `philip wiki graph` for detailed analysis.")
    else:
        click.echo("Health: OK")


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


@wiki.command()
@click.option("--dry-run", is_flag=True, help="Show changes without updating state.")
def sync(dry_run: bool) -> None:
    """Track changes and update sync state (mtime + content hash)."""
    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)

    paths.llm_wiki_dir.mkdir(parents=True, exist_ok=True)

    state = load_sync_state(paths.sync_state)
    result = compute_sync([paths.wiki, paths.contexts], root, state)

    total_changes = len(result.added) + len(result.modified) + len(result.deleted)

    if total_changes == 0:
        click.echo("Everything up to date.")
        return

    if result.added:
        click.echo(f"Added ({len(result.added)}):")
        for f in result.added:
            click.echo(f"  + {f}")
    if result.modified:
        click.echo(f"Modified ({len(result.modified)}):")
        for f in result.modified:
            click.echo(f"  ~ {f}")
    if result.deleted:
        click.echo(f"Deleted ({len(result.deleted)}):")
        for f in result.deleted:
            click.echo(f"  - {f}")

    click.echo(f"\nTotal: {total_changes} changes, {len(result.unchanged)} unchanged")

    if dry_run:
        click.echo("\n(dry run — state not updated)")
        return

    new_state = update_sync_state([paths.wiki, paths.contexts], root, state)
    save_sync_state(paths.sync_state, new_state)
    click.echo(f"\nSync state updated ({new_state.last_sync})")

    # Sync to DB9 if configured
    if config.db9 and config.db9.url:
        from philip.wiki.db9 import create_db9_client
        from philip.wiki.sync import content_hash as compute_hash
        from philip.wiki.wiki import parse_wiki_page

        db9 = create_db9_client(config)
        if db9:
            click.echo("\nSyncing to DB9...")
            try:
                db9.ensure_schema()

                # Upsert added/modified wiki pages
                wiki_changes = [
                    f for f in (result.added + result.modified)
                    if f.startswith("wiki/")
                ]
                for rel in wiki_changes:
                    file_path = root / rel
                    page = parse_wiki_page(file_path, paths.wiki)
                    h = compute_hash(file_path)
                    db9.upsert_page(page, h)
                    click.echo(f"  ↑ {rel}")

                # Delete removed wiki pages
                wiki_deleted = [f for f in result.deleted if f.startswith("wiki/")]
                for rel in wiki_deleted:
                    slug = rel.removeprefix("wiki/").removesuffix(".md")
                    db9.delete_page(slug)
                    click.echo(f"  ✕ {rel}")

                synced_count = len(wiki_changes) + len(wiki_deleted)
                click.echo(f"DB9 sync complete ({synced_count} pages)")
            except Exception as err:
                click.echo(f"DB9 sync failed: {err}", err=True)
            finally:
                db9.close()


# ---------------------------------------------------------------------------
# skill
# ---------------------------------------------------------------------------


@wiki.group(invoke_without_command=True)
@click.pass_context
def skill(ctx: click.Context) -> None:
    """Manage AI agent skills."""
    if ctx.invoked_subcommand is None:
        skills = list_skills()
        if not skills:
            click.echo("No skills found.")
            return
        click.echo("Available skills:")
        for s in skills:
            click.echo(f"  {s}")
        click.echo("")
        click.echo("Install all:  philip wiki skill install")
        click.echo("Show one:     philip wiki skill show <name>")


@skill.command()
@click.option("--claude", "target", flag_value="claude", help="Install to .claude/skills/ only.")
@click.option("--codex", "target", flag_value="codex", help="Install to .agents/skills/ only.")
@click.option("--dir", "workspace", default=None, help="Workspace directory (default: cwd).")
def install(target: str | None, workspace: str | None) -> None:
    """Install/upgrade skills in your AI agent workspace."""
    ws = Path(workspace) if workspace else Path.cwd()
    both = target is None

    if both or target == "claude":
        d = ws / ".claude" / "skills"
        result = install_skills_to(d)
        click.echo(f"Installed {len(result.installed)} skill{'s' if len(result.installed) != 1 else ''} to {d}/")
        for name in result.installed:
            click.echo(f"  {name}/SKILL.md")

    if both or target == "codex":
        d = ws / ".agents" / "skills"
        result = install_skills_to(d)
        if both:
            click.echo("")
        click.echo(f"Installed {len(result.installed)} skill{'s' if len(result.installed) != 1 else ''} to {d}/")
        for name in result.installed:
            click.echo(f"  {name}/SKILL.md")


@skill.command()
@click.argument("name")
def show(name: str) -> None:
    """Print skill content to stdout."""
    from philip.wiki.skills import _get_skills_dir

    skills_dir = _get_skills_dir()
    skill_path = skills_dir / name / "SKILL.md"
    if not skill_path.exists():
        available = list_skills()
        click.echo(f'Error: Skill "{name}" not found.', err=True)
        click.echo(f"Available: {', '.join(available)}", err=True)
        raise SystemExit(1)
    click.echo(skill_path.read_text(encoding="utf-8"))


@skill.command("list")
def list_cmd() -> None:
    """List all available skills."""
    skills = list_skills()
    if not skills:
        click.echo("No skills found.")
        return
    click.echo("Available skills:")
    for s in skills:
        click.echo(f"  {s}")
    click.echo("")
    click.echo("Install all:  philip wiki skill install")
    click.echo("Show one:     philip wiki skill show <name>")
