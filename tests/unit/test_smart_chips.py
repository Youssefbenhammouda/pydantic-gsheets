"""Tests for smart chip types and split_at_tokens."""
import pytest
from pydantic_gsheets.types.smart_chips import (
    split_at_tokens, fileSmartChip, youtubeSmartChip, richLinkProperties,
    SmartChipConfig, GSSmartChip, GS_SMARTCHIP,
)


def test_split_simple():
    result = split_at_tokens("hello @world")
    assert "@" in result.values()
    assert any(v == "hello " for v in result.values())


def test_split_multiple_tokens():
    result = split_at_tokens("@foo@")
    token_count = sum(1 for v in result.values() if v == "@")
    assert token_count == 2


def test_split_escaped_at():
    result = split_at_tokens("price \\@ cost")
    # no @ tokens — the \@ is a literal @
    assert "@" not in result.values()
    combined = "".join(result.values())
    assert "@ cost" in combined or "price @ cost" in combined


def test_file_smart_chip_to_dict():
    chip = fileSmartChip(uri="https://drive.google.com/file/abc")
    d = chip._to_dict()
    assert "richLinkProperties" in d["chip"]
    assert d["chip"]["richLinkProperties"]["uri"] == "https://drive.google.com/file/abc"


def test_youtube_chip_raises_not_implemented():
    chip = youtubeSmartChip(uri="https://youtube.com/watch?v=abc")
    with pytest.raises(NotImplementedError):
        chip._to_dict()


def test_gs_smartchip_alias():
    """GS_SMARTCHIP and GSSmartChip should be the same."""
    assert GS_SMARTCHIP is GSSmartChip


def test_smartchipconf_alias():
    from pydantic_gsheets.types.smart_chips import smartchipConf, SmartChipConfig
    assert smartchipConf is SmartChipConfig


def test_people_smart_chip_to_dict():
    from pydantic_gsheets.types.smart_chips import peopleSmartChip
    chip = peopleSmartChip(email="alice@example.com")
    d = chip._to_dict()
    assert d["chip"]["personProperties"]["email"] == "alice@example.com"
    assert d["chip"]["personProperties"]["displayFormat"] == "DEFAULT"


def test_event_smart_chip_raises_not_implemented():
    from pydantic_gsheets.types.smart_chips import eventSmartChip
    chip = eventSmartChip(uri="https://calendar.google.com/event/xyz")
    with pytest.raises(NotImplementedError):
        chip._to_dict()


def test_place_smart_chip_raises_not_implemented():
    from pydantic_gsheets.types.smart_chips import placeSmartChip
    chip = placeSmartChip(uri="https://maps.google.com/?q=Paris")
    with pytest.raises(NotImplementedError):
        chip._to_dict()


def test_rich_link_properties_to_dict():
    from pydantic_gsheets.types.smart_chips import richLinkProperties
    chip = richLinkProperties(uri="https://example.com")
    d = chip._to_dict()
    assert d["chip"]["richLinkProperties"]["uri"] == "https://example.com"


def test_split_empty_string():
    result = split_at_tokens("")
    assert result == {} or list(result.values()) == [""]


def test_split_at_only():
    result = split_at_tokens("@")
    assert "@" in result.values()


def test_split_no_at():
    result = split_at_tokens("hello world")
    assert "@" not in result.values()
    combined = "".join(result.values())
    assert "hello world" in combined


def test_split_mixed_escaped_unescaped():
    """\\@ becomes a literal '@' text segment; the second @ is an unescaped token."""
    result = split_at_tokens("\\@@end")
    combined = "".join(result.values())
    # Both the escaped and unescaped @ appear; "end" appears as trailing text
    assert "@" in combined
    assert "end" in combined
