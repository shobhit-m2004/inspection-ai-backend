from enum import Enum


class DocumentType(str, Enum):
    SOP = 'SOP'
    LOG = 'LOG'


class DocumentStatus(str, Enum):
    DRAFT = 'draft'
    APPROVED = 'approved'


class SessionStatus(str, Enum):
    ACTIVE = 'active'
    CLOSED = 'closed'
