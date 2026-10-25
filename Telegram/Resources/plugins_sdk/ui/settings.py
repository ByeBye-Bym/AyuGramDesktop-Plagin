# exteraGram-compatible settings items. Android-only fields are accepted and ignored.

from dataclasses import dataclass
from typing import Any, Callable, List, Optional


@dataclass
class Header:
    text: str


@dataclass
class Divider:
    text: Optional[str] = None


@dataclass
class Switch:
    key: str
    text: str
    default: bool = False
    subtext: Optional[str] = None
    icon: Optional[str] = None
    on_change: Optional[Callable[[bool], None]] = None
    on_long_click: Optional[Callable] = None
    link_alias: Optional[str] = None


@dataclass
class Selector:
    key: str
    text: str
    default: int = 0
    items: List[str] = None
    icon: Optional[str] = None
    on_change: Optional[Callable[[int], None]] = None
    on_long_click: Optional[Callable] = None
    link_alias: Optional[str] = None

    def __post_init__(self):
        self.items = self.items or []


@dataclass
class Input:
    key: str
    text: str
    default: Optional[str] = None
    subtext: Optional[str] = None
    icon: Optional[str] = None
    on_change: Optional[Callable[[str], None]] = None
    on_long_click: Optional[Callable] = None
    link_alias: Optional[str] = None


@dataclass
class EditText:
    key: str
    hint: str
    default: Optional[str] = None
    multiline: bool = False
    max_length: Optional[int] = None
    mask: Optional[str] = None
    on_change: Optional[Callable[[str], None]] = None


@dataclass
class Text:
    text: str
    subtext: Optional[str] = None
    icon: Optional[str] = None
    accent: bool = False
    red: bool = False
    on_click: Optional[Callable[[Any], None]] = None
    on_long_click: Optional[Callable] = None
    create_sub_fragment: Optional[Callable] = None
    link_alias: Optional[str] = None


class Custom:
    def __init__(self, *args, **kwargs):
        pass
