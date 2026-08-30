"""Color theme model loaded from the YAML theme file."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Theme(BaseModel):
    """A named palette applied to the terminal UI."""

    model_config = {"frozen": True}

    name: str
    dark: bool = True
    primary: str
    secondary: str | None = None
    accent: str | None = None
    foreground: str | None = None
    background: str | None = None
    surface: str | None = None
    panel: str | None = None
    success: str | None = None
    warning: str | None = None
    error: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)

    def to_textual_kwargs(self) -> dict[str, object]:
        """Return the fields Textual needs to build its own theme object."""
        return self.model_dump(exclude_none=True)
