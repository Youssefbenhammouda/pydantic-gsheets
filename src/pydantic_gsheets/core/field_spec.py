from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type, get_origin, get_type_hints
from typing import Annotated

from ..exceptions import SchemaError
from .descriptors import (
    GSFormat, GSIndex, GSParse, GSReadonly, GSRequired, GSTreatDashAsEmpty,
)


@dataclass
class _FieldSpec:
    name: str
    py_type: Any
    index: int
    required: Optional[GSRequired] = None
    readonly: bool = False
    parser: Optional[Callable] = None
    fmt: Optional[GSFormat] = None
    smartchip: Any = None           # smartchipConf — typed as Any to avoid circular import
    treat_dash_as_empty: bool = False


def _extract_field_specs(model_cls: type) -> dict[str, _FieldSpec]:
    """Parse Annotated type hints on a SheetRow subclass into _FieldSpec entries."""
    # Lazy import to avoid circular dependency
    from ..types.smart_chips import GS_SMARTCHIP, GSSmartChip, SmartChipConfig, smartChips, richLinkProperties, fileSmartChip

    hints = get_type_hints(model_cls, include_extras=True)
    specs: dict[str, _FieldSpec] = {}
    auto_index = 0

    for fname, hint in hints.items():
        if fname.startswith("_"):
            continue

        if get_origin(hint) is not Annotated:
            # Plain unannotated field — assign auto index
            specs[fname] = _FieldSpec(
                name=fname,
                py_type=hint,
                index=auto_index,
            )
            auto_index += 1
            continue

        base_type = hint.__args__[0]
        metadata = hint.__metadata__

        gs_index: Optional[int] = None
        required: Optional[GSRequired] = None
        readonly = False
        parser: Optional[Callable] = None
        fmt: Optional[GSFormat] = None
        smartchip_conf = None
        treat_dash_as_empty = False

        # Detect base type being smartChips
        try:
            is_smartchip_type = isinstance(base_type, type) and issubclass(base_type, smartChips)
        except TypeError:
            is_smartchip_type = False

        if is_smartchip_type:
            from ..types.smart_chips import SmartChipConfig
            smartchip_conf = SmartChipConfig(is_smartchips=True)

        for m in metadata:
            # Detect bare class usage (not instantiated)
            if m is GSRequired or (isinstance(m, type) and m is not GSRequired and issubclass(m, GSRequired)):
                raise SchemaError(
                    f"Field '{fname}': GSRequired must be used as an instance "
                    f"GSRequired(), not as a bare class."
                )
            if isinstance(m, GSIndex):
                gs_index = m.index
            elif isinstance(m, GSRequired):
                required = m
            elif isinstance(m, GSReadonly):
                readonly = True
            elif isinstance(m, GSParse):
                parser = m.func
            elif isinstance(m, GSFormat):
                fmt = m
            elif isinstance(m, GSTreatDashAsEmpty):
                treat_dash_as_empty = True
            elif isinstance(m, (GS_SMARTCHIP, GSSmartChip)):
                from ..types.smart_chips import SmartChipConfig, richLinkProperties, fileSmartChip
                # Auto-detect readonly: if chips other than fileSmartChip with richLinkProperties
                link_types = {x for x in m.smartchips if isinstance(x, type) and issubclass(x, richLinkProperties)}
                if len(link_types) > 1 or (len(link_types) == 1 and fileSmartChip not in link_types):
                    readonly = True
                smartchip_conf = SmartChipConfig(
                    is_smartchips=True,
                    smartchips=m.smartchips,
                    format_text=m.format_text,
                )

        idx = gs_index if gs_index is not None else auto_index
        auto_index = idx + 1

        specs[fname] = _FieldSpec(
            name=fname,
            py_type=base_type,
            index=idx,
            required=required,
            readonly=readonly,
            parser=parser,
            fmt=fmt,
            smartchip=smartchip_conf,
            treat_dash_as_empty=treat_dash_as_empty,
        )

    # Validate unique indices
    indices = [s.index for s in specs.values()]
    if len(indices) != len(set(indices)):
        dupes = list({i for i in indices if indices.count(i) > 1})
        raise SchemaError(
            f"Duplicate column indices {dupes} in {model_cls.__name__}."
        )

    return specs


def _max_index(specs: dict[str, _FieldSpec]) -> int:
    if not specs:
        return -1
    return max(s.index for s in specs.values())
