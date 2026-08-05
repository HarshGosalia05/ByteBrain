from pydantic import BaseModel
from typing import Any, Dict, List, Literal, Optional

class PreferenceVersionInfo(BaseModel):
    schema_version: int
    preference_version: int
    configuration_version: int
    last_modified: Optional[str] = None
    last_synced: Optional[str] = None
    restore_point: Optional[Dict[str, Any]] = None

class PreferenceActivityEntry(BaseModel):
    event: str
    at: str
    namespace: Optional[str] = None
    detail: Optional[str] = None

class PreferenceAuditEntry(BaseModel):
    action: str
    at: str
    namespace: Optional[str] = None
    summary: Optional[str] = None

class PreferenceDocument(BaseModel):
    namespaces: Dict[str, Any]
    versions: PreferenceVersionInfo
    activity: List[PreferenceActivityEntry]
    audit: List[PreferenceAuditEntry]

class SettingsResponse(BaseModel):
    namespaces: Dict[str, Any]
    metadata: PreferenceVersionInfo
    activity: List[PreferenceActivityEntry]

class SettingsUpdateResponse(BaseModel):
    namespaces: Dict[str, Any]
    metadata: PreferenceVersionInfo
    activity: List[PreferenceActivityEntry]
    highlights: List[str]

ResetLevel = Literal["dashboard", "analytics", "notifications", "accessibility", "workspace", "factory"]

class SettingsResetRequest(BaseModel):
    level: ResetLevel
    include_profile_extra: Optional[bool] = False

class SettingsBackupResponse(BaseModel):
    schema_version: int
    preference_version: int
    configuration_version: int
    exported_at: str
    namespaces: Dict[str, Any]

class SettingsImportRequest(BaseModel):
    payload: Dict[str, Any]
