"""Team service for loading and managing team definitions."""

import logging
import shutil
from pathlib import Path
from typing import List, Optional

import frontmatter

from cli_agent_orchestrator.constants import CAO_HOME_DIR
from cli_agent_orchestrator.models.team import Team

logger = logging.getLogger(__name__)

TEAMS_DIR = CAO_HOME_DIR / "teams"


def _ensure_teams_dir() -> Path:
    TEAMS_DIR.mkdir(parents=True, exist_ok=True)
    return TEAMS_DIR


def load_team(name: str) -> Team:
    """Load a team definition by name."""
    path = _ensure_teams_dir() / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Team '{name}' not found at {path}")
    return _parse_team_file(path)


def list_teams() -> List[Team]:
    """List all available teams."""
    teams_dir = _ensure_teams_dir()
    teams = []
    for path in sorted(teams_dir.glob("*.md")):
        try:
            teams.append(_parse_team_file(path))
        except Exception as e:
            logger.warning(f"Failed to parse team file {path}: {e}")
    return teams


def add_team(file_path: str) -> Team:
    """Install a team definition from a file path."""
    src = Path(file_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")

    team = _parse_team_file(src)
    dest = _ensure_teams_dir() / f"{team.name}.md"
    shutil.copy2(src, dest)
    logger.info(f"Installed team '{team.name}' to {dest}")
    return team


def remove_team(name: str) -> None:
    """Remove a team definition."""
    path = _ensure_teams_dir() / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Team '{name}' not found")
    path.unlink()
    logger.info(f"Removed team '{name}'")


def resolve_team_steering(team: Team) -> Optional[str]:
    """Read and concatenate all steering docs for a team.
    Returns the combined text or None if no steering docs."""
    if not team.steering and not team.context:
        return None

    parts = []
    if team.context:
        parts.append(f"## Team: {team.display_name or team.name}\n\n{team.context}")

    for path_str in team.steering:
        path = Path(path_str).expanduser().resolve()
        if path.exists():
            parts.append(f"## Steering: {path.name}\n\n{path.read_text()}")
        else:
            logger.warning(f"Steering doc not found: {path}")

    return "\n\n---\n\n".join(parts) if parts else None


def _parse_team_file(path: Path) -> Team:
    """Parse a team markdown file with YAML frontmatter."""
    post = frontmatter.loads(path.read_text())
    metadata = dict(post.metadata)

    if "name" not in metadata:
        metadata["name"] = path.stem

    return Team(
        name=metadata["name"],
        display_name=metadata.get("display_name"),
        home=metadata.get("home"),
        agents=metadata.get("agents", ["code_supervisor"]),
        steering=metadata.get("steering", []),
        provider=metadata.get("provider"),
        env=metadata.get("env", {}),
        context=post.content.strip(),
    )
