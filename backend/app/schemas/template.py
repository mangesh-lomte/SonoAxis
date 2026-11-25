from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class SectionDefinition(BaseModel):
    order: int
    key: str
    label: str
    heading: str
    is_required: bool = False
    default_text: Optional[str] = None

class TableColumnDef(BaseModel):
    key: str
    label: str
    col_index: int

class TableRowDef(BaseModel):
    key: str
    label: str
    row_index: int

class TableConfigDef(BaseModel):
    table_type: str  # "arterial_3col_table", "arterial_5col_table", "custom_table", "none"
    columns: List[TableColumnDef] = Field(default_factory=list)
    rows: List[TableRowDef] = Field(default_factory=list)

class TemplateResponse(BaseModel):
    id: str
    name: str
    gender: str
    category: str
    laterality: str
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    version: int = 1
    status: str = "APPROVED"  # "APPROVED", "DRAFT_CONFIG", "ARCHIVED"
    table_type: str = "none"
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    table_config: Optional[Dict[str, Any]] = None
    repeatable_config: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    is_built_in: bool = True
    is_shared: bool = False
    created_by_user_id: Optional[str] = None
    created_by_name: Optional[str] = None
    section_count: int = 0

class TemplateConfigUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    category: Optional[str] = None
    laterality: Optional[str] = None
    table_type: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    table_config: Optional[Dict[str, Any]] = None
    repeatable_config: Optional[Dict[str, Any]] = None

class TemplateApproveRequest(BaseModel):
    approved_by: str = "Clinical Director"

class DocStructureResponse(BaseModel):
    file_name: str
    paragraphs_count: int
    tables_count: int
    detected_headings: List[str] = Field(default_factory=list)
    detected_placeholders: List[str] = Field(default_factory=list)
    tables_summary: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_sections: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_category: str = "custom"
    suggested_laterality: str = "not_applicable"
    warnings: List[str] = Field(default_factory=list)
    has_floating_boxes: bool = False
