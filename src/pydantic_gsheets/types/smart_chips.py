"""Smart chip types for Google Sheets rich links, people chips, etc."""
from __future__ import annotations

import re
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class smartChip(BaseModel, ABC):
    __fieldName__: ClassVar[str]

    @abstractmethod
    def _to_dict(self) -> dict[Any, Any]: ...


# ---------------------------------------------------------------------------
# Concrete chip types
# ---------------------------------------------------------------------------

class richLinkProperties(smartChip):
    __fieldName__: ClassVar[str] = "richLinkProperties"
    uri: str = Field(..., description="The URI of the rich link.")

    def _to_dict(self) -> dict:
        return {
            "chip": {
                "richLinkProperties": {"uri": self.uri}
            }
        }


class personProperties(smartChip):
    __fieldName__: ClassVar[str] = "personProperties"

    class displayFormat(Enum):
        DEFAULT = "DEFAULT"
        LAST_NAME_COMMA_FIRST_NAME = "LAST_NAME_COMMA_FIRST_NAME"
        EMAIL = "EMAIL"

    email: str = Field(..., description="The email address of the person.")
    display_format: displayFormat = Field(
        default=displayFormat.DEFAULT,
        description="The display format for the person.",
    )

    def _to_dict(self) -> dict:
        return {
            "chip": {
                "personProperties": {
                    "email": self.email,
                    "displayFormat": self.display_format.value,
                }
            }
        }


class peopleSmartChip(personProperties):
    """Alias kept for backward compatibility."""
    pass


class fileSmartChip(richLinkProperties):
    """Smart chip linking to a Google Drive file. Supports write."""
    pass


class eventSmartChip(richLinkProperties):
    def _to_dict(self) -> dict:
        raise NotImplementedError(
            "Only links to Google Drive files can be written as chips. "
            "eventSmartChip is read-only."
        )


class placeSmartChip(richLinkProperties):
    def _to_dict(self) -> dict:
        raise NotImplementedError(
            "Only links to Google Drive files can be written as chips. "
            "placeSmartChip is read-only."
        )


class youtubeSmartChip(richLinkProperties):
    def _to_dict(self) -> dict:
        raise NotImplementedError(
            "Only links to Google Drive files can be written as chips. "
            "youtubeSmartChip is read-only."
        )


# PascalCase aliases
RichLinkProperties = richLinkProperties
FileSmartChip = fileSmartChip
PeopleSmartChip = peopleSmartChip
EventSmartChip = eventSmartChip
PlaceSmartChip = placeSmartChip
YouTubeSmartChip = youtubeSmartChip


# ---------------------------------------------------------------------------
# Container / config
# ---------------------------------------------------------------------------

class SmartChips(BaseModel):
    display_text: Optional[str] = Field(default=None)
    format_text: Optional[str] = None
    chipRuns: list[smartChip] = []


# backward-compat alias
smartChips = SmartChips


@dataclass
class GSSmartChip:
    """Annotation marker: declare a field as containing smart chips."""
    format_text: str = "@"
    smartchips: list[type[smartChip]] = field(default_factory=list)


# simple alias — old name kept for backward compat
GS_SMARTCHIP = GSSmartChip


class SmartChipConfig(BaseModel):
    is_smartchips: bool = False
    smartchips: list[type[smartChip]] = []
    format_text: str = "@"


# backward-compat alias
smartchipConf = SmartChipConfig


# ---------------------------------------------------------------------------
# Token splitting helper
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"(?<!\\)@")


def split_at_tokens(s: str) -> dict[int, str]:
    """
    Split *s* at unescaped '@' characters.

    Returns a dict mapping each segment's start index to the segment text or '@'.
    Escaped '\\@' is returned as a literal '@' within the segment text.
    """
    result: dict[int, str] = {}
    pos = 0
    for m in _TOKEN_RE.finditer(s):
        start = m.start()
        if start > pos:
            result[pos] = s[pos:start].replace("\\@", "@")
        result[start] = "@"
        pos = m.end()
    if pos < len(s):
        result[pos] = s[pos:].replace("\\@", "@")
    return result
