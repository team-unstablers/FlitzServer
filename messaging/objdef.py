from typing import List, Optional, TypedDict, Literal, Dict

from dataclasses import dataclass, asdict

from dacite import from_dict

# Object definitions for DirectMessage.content JSON field

"""typescript
export type DirectMessageTextContent = {
    type: 'text'
    text: string
} 

export type DirectMessageAttachmentContent = {
    type: 'attachment'
    attachment_id: string
}

export type DirectMessageContent = DirectMessageTextContent | DirectMessageAttachmentContent
"""

DirectMessageTextContentType = Literal["text"]
DirectMessageAttachmentContentType = Literal["attachment"]

@dataclass
class DirectMessageTextContent:
    type: DirectMessageTextContentType
    text: str

    def as_dict(self) -> dict:
        return asdict(self)

@dataclass
class DirectMessageAttachmentContent:
    type: DirectMessageAttachmentContentType

    attachment_type: str
    attachment_id: str

    width: int
    height: int

    public_url: Optional[str]
    thumbnail_url: Optional[str]

    def as_dict(self) -> dict:
        return asdict(self)

DirectMessageContent = DirectMessageTextContent | DirectMessageAttachmentContent

def load_direct_message_content(data: Dict) -> DirectMessageContent:
    if data["type"] == "text":
        return from_dict(data_class=DirectMessageTextContent, data=data)
    elif data["type"] == "attachment":
        return from_dict(data_class=DirectMessageAttachmentContent, data=data)
    else:
        raise ValueError(f"Unknown content type: {data['type']}")
