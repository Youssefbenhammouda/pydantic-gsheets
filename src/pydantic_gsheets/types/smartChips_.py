from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field
from typing import Any, ClassVar
from ..exceptions import noWriteSupport
from abc import ABC, abstractmethod

class smartChip(BaseModel,ABC):
    __fieldName__: ClassVar[str]
    @abstractmethod
    def _to_dict(self) -> dict[Any,Any]:...
@dataclass
class GS_SMARTCHIP:
    
    format_text: str = Field(default="@", description="The format text for the smart chip.")
    smartchips:list[type[smartChip]] = Field(default_factory=list, description="List of smart chips associated with the display text.")

class smartchipConf(BaseModel):
    is_smartchips: bool = False
    smartchips:list[type[smartChip]] = []
    format_text: str = "@"
class smartChips(BaseModel):
    display_text: str = Field(..., description="The display text for the rich link.")
    format_text: str 
    chipRuns: list[smartChip] = []
class richLinkProperties(smartChip):
    __fieldName__: ClassVar[str] = "richLinkProperties"

    uri: str= Field(..., description="The URI of the rich link.")
    #startIndex: int = Field(..., description="The start index of the rich link.")

    def _to_dict(self):
        return  {
                        #"startIndex": self.startIndex,
                        "chip": {
                          "richLinkProperties": {
                            "uri": self.uri
                          }
                        }
                    }

class personProperties(smartChip):
    __fieldName__: ClassVar[str] = "personProperties"
    class displayFormat(Enum):
        DEFAULT = "DEFAULT"
        LAST_NAME_COMMA_FIRST_NAME = "LAST_NAME_COMMA_FIRST_NAME"
        EMAIL = "EMAIL"

    email: str = Field(..., description="The email address of the person.")
    display_format: displayFormat = Field(default=displayFormat.DEFAULT, description="The display format for the person.")
    
    def _to_dict(self):
        return {
                        "chip": {
                          "personProperties": {
                            "email": self.email,
                            "displayFormat": self.display_format.value
                          }
                        }
                      }


class peopleSmartChip(personProperties):
    pass

class fileSmartChip(richLinkProperties):
    pass

class eventSmartChip(richLinkProperties):
    def _to_dict(self):
        raise noWriteSupport()
class placeSmartChip(richLinkProperties):
    def _to_dict(self):
        raise noWriteSupport()

class youtubeSmartChip(richLinkProperties):
    def _to_dict(self):
        raise noWriteSupport()



#helpers

def split_at_tokens(s: str) -> dict[int, str]:
    """
    Splits a string into chunks keyed by starting index in the original string.
    Escaped form '\\@' is treated as a literal '@'.
    """
    result = {}
    buffer = []
    seg_start = 0
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "@":
            buffer.append("@")
            i += 2
        elif s[i] == "@":
            # flush buffer before the token
            if buffer:
                result[seg_start] = "".join(buffer)
                buffer = []
            result[i] = "@"
            i += 1
            seg_start = i
        else:
            if not buffer:
                seg_start = i
            buffer.append(s[i])
            i += 1
    if buffer:
        result[seg_start] = "".join(buffer)
    return result
