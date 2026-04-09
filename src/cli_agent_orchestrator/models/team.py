"""Team model for bounded context sessions."""

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Team(BaseModel):
    """A team is a named bounded context that bundles working directory,
    agent profiles, steering docs, and environment variables."""

    name: str = Field(..., description="Unique team identifier (e.g., 'octopus')")
    display_name: Optional[str] = Field(None, description="Human-readable name")
    home: Optional[str] = Field(None, description="Working directory for all sessions")
    agents: List[str] = Field(default_factory=lambda: ["code_supervisor"])
    steering: List[str] = Field(default_factory=list, description="Paths to steering docs")
    provider: Optional[str] = Field(None, description="Default provider override")
    env: Dict[str, str] = Field(default_factory=dict, description="Extra env vars")
    context: str = Field("", description="Team context text (markdown body)")

    @property
    def resolved_home(self) -> Optional[Path]:
        """Resolve home path with ~ expansion."""
        if self.home:
            return Path(self.home).expanduser().resolve()
        return None
