"""Optional declarative UI metadata; it never adds or proves puzzle constraints."""

from dataclasses import asdict, dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class UiChannel:
    name: str
    kind: str


@dataclass(frozen=True)
class UiRequirements:
    topology: str = "rectangular-cells"
    channels: tuple[UiChannel, ...] = (UiChannel("answer", "binary-cells"),)
    max_cells: int = 9


@dataclass(frozen=True)
class UiParameter:
    name: str
    label: str
    kind: Literal["integer", "boolean"]
    default: int | bool
    minimum: int = 0
    maximum: int | Literal["area", "edges"] = "area"

    def validate(self, value: Any, *, area: int, edges: int | None = None) -> None:
        if self.kind == "boolean":
            if type(value) is not bool:
                raise ValueError(f"{self.name} must be a boolean")
        elif self.kind == "integer":
            maximum = area if self.maximum == "area" else edges if self.maximum == "edges" else self.maximum
            if maximum is None:
                raise ValueError("An edge bound requires the number of grid edges")
            if type(value) is not int or not self.minimum <= value <= maximum:
                raise ValueError(f"{self.name} must be an integer in {self.minimum}..{maximum}")
        else:
            raise ValueError(f"Unsupported parameter kind: {self.kind}")


@dataclass(frozen=True)
class RuleUi:
    identifier: str
    label: str
    summary: str
    parameters: tuple[UiParameter, ...] = ()
    requirements: UiRequirements = UiRequirements()
    required: bool = False

    def record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClueUi:
    identifier: str
    label: str
    requirements: UiRequirements


def merge_requirements(requirements: list[UiRequirements], *, supported: dict[str, str]) -> UiRequirements:
    """Unify shared channel types; renderer support is separate from solvability."""
    if not requirements:
        raise ValueError("At least one UI requirement is needed")
    topology = requirements[0].topology
    channels: dict[str, str] = {}
    if any(type(item.max_cells) is not int or item.max_cells < 1 for item in requirements):
        raise ValueError("UI cell limits must be positive integers")
    limit = min(item.max_cells for item in requirements)
    for item in requirements:
        if item.topology != topology:
            raise ValueError("Incompatible board topologies")
        for channel in item.channels:
            if channel.name in channels and channels[channel.name] != channel.kind:
                raise ValueError(f"Conflicting UI channel: {channel.name}")
            channels[channel.name] = channel.kind
    if topology != "rectangular-cells":
        raise ValueError(f"Unsupported board topology: {topology}")
    for name, kind in channels.items():
        if supported.get(name) != kind:
            raise ValueError(f"Unsupported UI channel: {name}/{kind}")
    return UiRequirements(topology, tuple(UiChannel(name, kind) for name, kind in sorted(channels.items())), limit)
