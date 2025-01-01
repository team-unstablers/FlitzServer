from typing import List, Optional, TypedDict, Literal, Dict

from enum import Enum
from dataclasses import dataclass, asdict


@dataclass
class ElementSize:
    width: float
    height: float

@dataclass
class Position:
    x: float
    y: float

@dataclass
class Transform:
    position: Position
    scale: float
    rotation: float

@dataclass
class AssetReference:
    id: str
    public_url: Optional[str]

ImageElementType = Literal["image"]
TextElementType = Literal["text"]

@dataclass
class ImageElement:
    type: ImageElementType
    transform: Transform

    source: AssetReference
    size: ElementSize


@dataclass
class TextElement:
    type: TextElementType
    transform: Transform

    text: str

Element = ImageElement | TextElement

class CardSchemaVersion(Enum):
    EXPERIMENTAL = "0.9-experimental"

    V1 = "1.0"


@dataclass
class CardObject:
    schema_version: str

    background: Optional[AssetReference]
    elements: List[Element]

    properties: Dict[str, str]

    @staticmethod
    def create_empty(version: CardSchemaVersion = CardSchemaVersion.V1) -> "CardObject":
        return CardObject(
            schema_version=version.value,
            background=None,
            elements=[],
            properties={}
        )

    def as_dict(self) -> dict:
        return asdict(self)

    def sanity_check(self):
        return True

    def extract_asset_references(self) -> List[AssetReference]:
        references = []

        if self.background is not None:
            references.append(self.background)

        for element in self.elements:
            if isinstance(element, ImageElement):
                references.append(element.source)

        return references



