"""Skill file management — install, list, show bundled agent skills."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


def _get_skills_dir() -> Path:
    """Return the built-in skills directory within the philip package."""
    # philip/capabilities/wiki/skills.py -> ... -> philip -> philip/skills/
    return Path(__file__).resolve().parent.parent.parent / "skills"


def list_skills(skills_dir: str | Path | None = None) -> list[str]:
    """List available skill names (directories containing SKILL.md)."""
    sd = Path(skills_dir) if skills_dir else _get_skills_dir()
    if not sd.exists():
        return []
    return sorted(
        d.name
        for d in sd.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


@dataclass
class InstallResult:
    installed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def install_skills_to(
    target_dir: str | Path,
    *,
    overwrite: bool = True,
    skills_dir: str | Path | None = None,
) -> InstallResult:
    """Install bundled skills to *target_dir*.

    Copies each ``<skills_dir>/<name>/SKILL.md`` to ``<target_dir>/<name>/SKILL.md``.
    """
    sd = Path(skills_dir) if skills_dir else _get_skills_dir()
    if not sd.exists():
        raise FileNotFoundError("Skills directory not found. Package may be corrupted.")

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    result = InstallResult()

    for skill_dir in sorted(sd.iterdir()):
        if not skill_dir.is_dir():
            continue
        src = skill_dir / "SKILL.md"
        if not src.exists():
            continue

        skill_name = skill_dir.name
        dest_dir = target / skill_name
        dest = dest_dir / "SKILL.md"

        if not overwrite and dest.exists():
            result.skipped.append(skill_name)
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        result.installed.append(skill_name)

    return result
