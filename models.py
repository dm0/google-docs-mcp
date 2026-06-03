from enum import Enum
from typing import Annotated, Union, Literal
from typing_extensions import Self
from pydantic import BaseModel, Field, Discriminator, Tag, RootModel, model_validator, BeforeValidator

HEADING_LEVELS = {
    "TITLE": "Title",
    "SUBTITLE": "Subtitle",
    "HEADING_1": "H1",
    "HEADING_2": "H2",
    "HEADING_3": "H3",
    "HEADING_4": "H4",
    "HEADING_5": "H5",
    "HEADING_6": "H6",
    "NORMAL_TEXT": "(no heading)"
}
HEADING_ORDER = dict(zip(HEADING_LEVELS.values(), range(len(HEADING_LEVELS))))

class DocumentTreeSection(BaseModel):
    """A document section as appears in document tree"""
    title: str
    id: str
    level: str
    ancestor_ids: list[str] = []

    @property
    def level_index(self) -> int:
        return HEADING_ORDER.get(self.level, len(HEADING_LEVELS))


class DocumentSection(DocumentTreeSection):
    """An extended version that includes full parsed document details"""

    markdown: str
    children: list[Self] = []
    parent: Annotated[Self | None, Field(exclude=True)] = None

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()

    def subtree(self):
        yield self
        for child in self.children:
            yield from child.subtree()

    def subtree_markdown(self):
        return "\n\n".join([self.markdown, *[child.subtree_markdown() for child in self.children]])


class GoogleDocumentImageProperties(BaseModel):
    contentUri: str
    sourceUri: str | None = None


class GoogleDocumentEmbeddedObject(BaseModel):
    title: str | None = None
    description: str | None = None
    imageProperties: GoogleDocumentImageProperties | None = None


class GoogleDocumentInlineObjectProperties(BaseModel):
    embeddedObject: GoogleDocumentEmbeddedObject


class GoogleDocumentInlineObject(BaseModel):
    objectId: str
    inlineObjectProperties: GoogleDocumentInlineObjectProperties


class GoogleDocumentGlyphType(Enum):
    GLYPH_TYPE_UNSPECIFIED = "GLYPH_TYPE_UNSPECIFIED"
    NONE = "NONE"
    DECIMAL = "DECIMAL"
    ZERO_DECIMAL = "ZERO_DECIMAL"
    UPPER_ALPHA = "UPPER_ALPHA"
    ALPHA = "ALPHA"
    UPPER_ROMAN = "UPPER_ROMAN"
    ROMAN = "ROMAN"



class GoogleDocumentNestingLevel(BaseModel):
    glyphFormat: str
    glyphSymbol: str | None = None
    glyphType: GoogleDocumentGlyphType = GoogleDocumentGlyphType.GLYPH_TYPE_UNSPECIFIED


class GoogleDocumentListProperties(BaseModel):
    nestingLevels: list[GoogleDocumentNestingLevel]


class GoogleDocumentList(BaseModel):
    listProperties: GoogleDocumentListProperties


class GoogleDocumentStructuralElement(BaseModel):
    type: Literal["base"] = "base"
    startIndex: int = 0
    endIndex: int = 0


class GoogleDocumentBaselineOffset(Enum):
    # The text's baseline offset is inherited from the parent.
    BASELINE_OFFSET_UNSPECIFIED = "BASELINE_OFFSET_UNSPECIFIED"
    # The text is not vertically offset.
    NONE = "NONE"
    # The text is vertically offset upwards (superscript).
    SUPERSCRIPT = "SUPERSCRIPT"
    # The text is vertically offset downwards (subscript).
    SUBSCRIPT = "SUBSCRIPT"


class GoogleDocumentLink(BaseModel):
    url: str | None = None  # The only supported link type - external

class GoogleDocumentTextStyle(BaseModel):
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    smallCaps: bool = False
    baselineOffset: GoogleDocumentBaselineOffset = GoogleDocumentBaselineOffset.BASELINE_OFFSET_UNSPECIFIED
    link: GoogleDocumentLink | None = None

class GoogleDocumentTextRun(GoogleDocumentStructuralElement):
    type: Literal["textRun"] = "textRun"
    content: str
    textStyle: GoogleDocumentTextStyle


class GoogleDocumentHorizontalRule(GoogleDocumentStructuralElement):
    type: Literal["horizontalRule"] = "horizontalRule"
    textStyle: GoogleDocumentTextStyle


class GoogleDocumentInlineObjectElement(GoogleDocumentStructuralElement):
    type: Literal["inlineObjectElement"] = "inlineObjectElement"
    inlineObjectId: str
    textStyle: GoogleDocumentTextStyle


class GoogleDocumentNamedStyleType(Enum):
    TITLE = "TITLE"
    SUBTITLE = "SUBTITLE"
    HEADING_1 = "HEADING_1"
    HEADING_2 = "HEADING_2"
    HEADING_3 = "HEADING_3"
    HEADING_4 = "HEADING_4"
    HEADING_5 = "HEADING_5"
    HEADING_6 = "HEADING_6"
    NORMAL_TEXT = "NORMAL_TEXT"
    NAMED_STYLE_TYPE_UNSPECIFIED = "NAMED_STYLE_TYPE_UNSPECIFIED"


class GoogleDocumentAlignment(Enum):
    ALIGNMENT_UNSPECIFIED = "ALIGNMENT_UNSPECIFIED"
    START = "START"
    CENTER = "CENTER"
    END = "END"
    JUSTIFIED = "JUSTIFIED"


class GoogleDocumentParagraphStyle(BaseModel):
    headingId: str | None = None
    namedStyleType: GoogleDocumentNamedStyleType = GoogleDocumentNamedStyleType.NAMED_STYLE_TYPE_UNSPECIFIED
    alignment: GoogleDocumentAlignment = GoogleDocumentAlignment.ALIGNMENT_UNSPECIFIED


class GoogleDocumentBullet(BaseModel):
    listId: str
    nestingLevel: int = 0
    textStyle: GoogleDocumentTextStyle


def _unnest_paragraph_element(data: dict) -> dict:
    kinds = {"textRun", "horizontalRule," "inlineObjectElement"}
    present_kinds = kinds.intersection(data.keys())
    if present_kinds:
        kind = next(iter(present_kinds))
        inner_payload = data.pop(kind)
    else:
        kind = "base"
        inner_payload = {}
    return {
        "type": kind,
        **data,
        **inner_payload
    }


GoogleDocumentParagraphElement = Annotated[
    Annotated[
        Union[
            GoogleDocumentTextRun,
            GoogleDocumentHorizontalRule,
            GoogleDocumentInlineObjectElement,
            GoogleDocumentStructuralElement,
        ],
        Discriminator("type")
    ],
    BeforeValidator(_unnest_paragraph_element)
]


class GoogleDocumentParagraph(GoogleDocumentStructuralElement):
    type: Literal["paragraph"] = "paragraph"
    elements: list[GoogleDocumentParagraphElement]
    paragraphStyle: GoogleDocumentParagraphStyle
    bullet: GoogleDocumentBullet | None = None


def _unnest_document_content(data: dict) -> dict:
    kinds = {"paragraph", "table"}
    present_kinds = kinds.intersection(data.keys())
    if present_kinds:
        kind = next(iter(present_kinds))
        inner_payload = data.pop(kind)
    else:
        kind = "base"
        inner_payload = {}
    return {
        "type": kind,
        **data,
        **inner_payload
    }


GoogleDocumentContent = Annotated[
    Annotated[
        Union[
            GoogleDocumentParagraph,
            'GoogleDocumentTable',
            GoogleDocumentStructuralElement,
        ],
        Discriminator("type")
    ],
    BeforeValidator(_unnest_document_content)
]


class GoogleDocumentTableCellStyle(BaseModel):
    rowSpan: int
    columnSpan: int


class GoogleDocumentTableCell(GoogleDocumentStructuralElement):
    content: list[GoogleDocumentContent]
    tableCellStyle: GoogleDocumentTableCellStyle


class GoogleDocumentTableRow(GoogleDocumentStructuralElement):
    tableCells: list[GoogleDocumentTableCell]


class GoogleDocumentTable(GoogleDocumentStructuralElement):
    type: Literal["table"] = "table"
    rows: int
    columns: int
    tableRows: list[GoogleDocumentTableRow]


class GoogleDocumentBody(BaseModel):
    content: list[GoogleDocumentContent]


class GoogleDocument(BaseModel):
    title: str
    body: GoogleDocumentBody
    lists: dict[str, GoogleDocumentList]
    inlineObjects: dict[str, GoogleDocumentInlineObject]
    revisionId: str
    documentId: str
