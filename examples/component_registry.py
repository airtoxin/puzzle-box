"""Explicit trusted codecs for bounded, flat component parameters.

Registration is Python configuration, never read from puzzle files. Constructors
and builders are trusted code; this registry is not a sandbox for that code.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from inspect import signature
import re
from typing import Any


@dataclass(frozen=True)
class IntParam:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if type(self.minimum) is not int or type(self.maximum) is not int or self.minimum > self.maximum:
            raise ValueError("Integer parameter bounds must be integers in ascending order")

    def check(self, value: Any) -> None:
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise ValueError(f"Expected an integer between {self.minimum} and {self.maximum}")


@dataclass(frozen=True)
class ChoiceParam:
    choices: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.choices, (tuple, list)):
            raise ValueError("Choices must be a tuple or list of strings")
        choices = tuple(self.choices)
        if not choices or any(type(c) is not str for c in choices) or len(set(choices)) != len(choices):
            raise ValueError("Choices must be distinct strings in a nonempty sequence")
        object.__setattr__(self, "choices", choices)

    def check(self, value: Any) -> None:
        if type(value) is not str or value not in self.choices:
            raise ValueError(f"Expected one of {self.choices}")


@dataclass(frozen=True)
class BoolParam:
    def check(self, value: Any) -> None:
        if type(value) is not bool:
            raise ValueError("Expected a boolean")


type Parameter = IntParam | ChoiceParam | BoolParam


@dataclass(frozen=True)
class _Entry:
    identifier: str
    builder_type: type
    parameters: tuple[tuple[str, Parameter], ...]

    def values(self, data: dict[str, Any]) -> dict[str, Any]:
        if set(data) != {"id", *(name for name, _ in self.parameters)}:
            raise ValueError(f"Invalid component fields for {self.identifier}")
        values = {}
        for name, parameter in self.parameters:
            try:
                parameter.check(data[name])
            except ValueError as exc:
                raise ValueError(f"{self.identifier}.{name}: {exc}") from exc
            values[name] = data[name]
        return values


@dataclass(frozen=True)
class ComponentRegistry:
    """An immutable registry; with_component returns a new independent value."""

    _entries: tuple[_Entry, ...] = field(default=(), init=False, repr=False)

    def require_base(self, baseline: ComponentRegistry) -> None:
        if any(entry not in self._entries for entry in baseline._entries):
            raise ValueError("Registry must preserve all built-in component IDs, types and parameter schemas")

    def with_component(self, identifier: str, builder_type: type, **parameters: Parameter) -> ComponentRegistry:
        if (type(identifier) is not str
                or re.fullmatch(r"[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)*/v[1-9][0-9]*", identifier) is None):
            raise ValueError("Component ID must be a lowercase path ending in /vN, for example acme/row-band/v1")
        if any(e.identifier == identifier for e in self._entries):
            raise ValueError(f"Component ID already registered: {identifier}")
        if any(e.builder_type is builder_type for e in self._entries):
            raise ValueError("Component type already registered; aliases would make export ambiguous")
        if (not isinstance(builder_type, type) or not is_dataclass(builder_type)
                or not getattr(builder_type, "__dataclass_params__").frozen
                or not any("__call__" in t.__dict__ for t in builder_type.__mro__)):
            raise ValueError("Component type must be a frozen callable dataclass")
        declared = fields(builder_type)
        constructor = signature(builder_type)
        if ("id" in parameters or any(not f.init for f in declared)
                or set(parameters) != {f.name for f in declared}
                or set(constructor.parameters) != set(parameters)):
            raise ValueError("Parameters must match all dataclass constructor fields; id is reserved")
        try:
            constructor.bind(**dict.fromkeys(parameters))
        except TypeError as exc:
            raise ValueError("Component constructor must accept parameter fields as keywords") from exc
        if any(type(p) not in (IntParam, ChoiceParam, BoolParam) for p in parameters.values()):
            raise ValueError("Use only IntParam, ChoiceParam or BoolParam validators")
        entry = _Entry(identifier, builder_type, tuple(parameters.items()))
        extended = ComponentRegistry()
        object.__setattr__(extended, "_entries", (*self._entries, entry))
        return extended

    def decode(self, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("A component must be an object")
        identifier = data.get("id")
        if type(identifier) is not str:
            raise ValueError("Unknown component ID/version")
        entry = next((e for e in self._entries if e.identifier == identifier), None)
        if entry is None:
            raise ValueError(f"Unknown component ID/version: {identifier}")
        values = entry.values(data)  # All fields/types/ranges checked before trusted construction.
        builder = entry.builder_type(**values)
        # The known constructor may enforce cross-field rules but must preserve
        # parameters. Reject normalization that changes the meaning of saved data.
        if type(builder) is not entry.builder_type or self._record(entry, builder) != data:
            raise ValueError("Component constructor must preserve its parameter values")
        return builder

    @staticmethod
    def _record(entry: _Entry, builder: Any) -> dict[str, Any]:
        record = {"id": entry.identifier, **{name: getattr(builder, name) for name, _ in entry.parameters}}
        entry.values(record)
        return record

    def encode(self, builder: Any) -> dict[str, Any]:
        entry = next((e for e in self._entries if e.builder_type is type(builder)), None)
        if entry is None:
            raise ValueError("Cannot save arbitrary Python builders or unregistered component subclasses")
        return self._record(entry, builder)
