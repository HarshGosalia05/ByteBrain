import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.repositories.settings_repo import SettingsRepository


class PreferenceValidationError(ValueError):
    pass


# Namespaces whose changes are configuration-affecting for the faculty workspace
# (bump `configuration_version` on write). Profile extras and personalization
# only bump `preference_version`.
_CONFIGURATION_NAMESPACES = {"analytics", "workspace", "export", "notifications", "dashboard"}

# Namespaces included in preference-only configuration backups/imports.
# Security (session data) and profile_extra (identity extension) are excluded.
_BACKUP_NAMESPACES = ("workspace", "dashboard", "analytics", "notifications", "export", "accessibility", "personalization")

# Scoped reset levels. `factory` expands to every namespace (optionally including
# profile_extra when explicitly confirmed by the caller).
_RESET_LEVELS = {
    "dashboard": ("dashboard",),
    "analytics": ("analytics",),
    "notifications": ("notifications",),
    "accessibility": ("accessibility",),
    "workspace": ("workspace",),
    "factory": None,
}

# Fields written exclusively by the engine (recents, history, activity, sessions...).
# A user PATCH targeting these is rejected.
_AUTO_MANAGED = {
    "workspace": {"saved_workspaces"},
    "dashboard": {"favorites", "recents", "quick_launch", "pinned_widgets", "hidden_widgets", "collapsed_widgets", "widget_order"},
    "analytics": {"applied_bounds"},
    "notifications": {"history"},
    "personalization": {"recent_searches", "favorite_filters", "favorite_subjects", "pinned_students", "recent_pages", "quick_launch_shortcuts"},
    "security": {"password_updated_at", "last_login", "current_session", "sessions"},
}

_NAMESPACE_SPECS: Dict[str, Dict[str, Any]] = {
    "workspace": {
        "dashboard_layout": {"t": "enum", "values": ["single", "two_column", "grid"], "default": "grid"},
        "compact_mode": {"t": "bool", "default": False},
        "comfortable_mode": {"t": "bool", "default": False},
        "table_density": {"t": "enum", "values": ["compact", "default", "comfortable"], "default": "default"},
        "card_density": {"t": "enum", "values": ["compact", "default", "comfortable"], "default": "default"},
        "sidebar_default_state": {"t": "enum", "values": ["expanded", "collapsed"], "default": "expanded"},
        "sticky_filters": {"t": "bool", "default": False},
        "default_page_size": {"t": "enum", "values": [10, 20, 50], "default": 20},
        "saved_workspaces": {"t": "list", "default": []},
    },
    "dashboard": {
        "default_semester": {"t": "int", "bounds": [0, 8], "default": 0},
        "default_academic_year": {"t": "string", "max_length": 20, "default": ""},
        "default_compare": {"t": "bool", "default": False},
        "default_chart": {"t": "enum", "values": ["bar", "line", "donut"], "default": "bar"},
        "favorites": {"t": "list", "default": []},
        "recents": {"t": "list", "default": []},
        "quick_launch": {"t": "list", "default": []},
        "pinned_widgets": {"t": "list", "default": []},
        "hidden_widgets": {"t": "list", "default": []},
        "collapsed_widgets": {"t": "list", "default": []},
        "widget_order": {"t": "list", "default": []},
    },
    "analytics": {
        "attendance_threshold_override": {
            "t": "number",
            "admin_bounds": settings.SETTINGS_ATTENDANCE_THRESHOLD_BOUNDS,
            "nullable": True,
            "default": None,
        },
        "performance_threshold_override": {
            "t": "number",
            "admin_bounds": settings.SETTINGS_PERFORMANCE_THRESHOLD_BOUNDS,
            "nullable": True,
            "default": None,
        },
        "workload_capacity_hours_override": {
            "t": "number",
            "admin_bounds": settings.SETTINGS_WORKLOAD_CAPACITY_BOUNDS,
            "nullable": True,
            "default": None,
        },
        "overload_threshold_override": {
            "t": "number",
            "admin_bounds": settings.SETTINGS_WORKLOAD_OVERLOAD_BOUNDS,
            "nullable": True,
            "default": None,
        },
        "underutilized_threshold_override": {
            "t": "number",
            "admin_bounds": settings.SETTINGS_WORKLOAD_UNDERUTILIZED_BOUNDS,
            "nullable": True,
            "default": None,
        },
        "default_compare_mode": {"t": "enum", "values": ["auto", "on", "off"], "default": "auto"},
        "chart_tooltips": {"t": "bool", "default": True},
        "chart_legend_position": {"t": "enum", "values": ["bottom", "right", "top", "hidden"], "default": "bottom"},
        "auto_refresh": {"t": "bool", "default": False},
        "sorting_field": {"t": "enum", "values": ["attendance", "performance", "pass_rate", "credits", "students"], "default": "attendance"},
        "sorting_order": {"t": "enum", "values": ["desc", "asc"], "default": "desc"},
        "table_page_size": {"t": "enum", "values": [10, 20, 50], "default": 20},
        "table_density": {"t": "enum", "values": ["compact", "default", "comfortable"], "default": "default"},
        "applied_bounds": {"t": "record", "fields": {}, "default": {}},
    },
    "notifications": {
        "rules": {"t": "list", "max_length": 50, "default": []},
        "quiet_hours": {
            "t": "record",
            "fields": {
                "enabled": {"t": "bool", "default": False},
                "start": {"t": "string", "max_length": 5, "default": "22:00"},
                "end": {"t": "string", "max_length": 5, "default": "07:00"},
            },
            "default": {"enabled": False, "start": "22:00", "end": "07:00"},
        },
        "do_not_disturb": {
            "t": "record",
            "fields": {
                "enabled": {"t": "bool", "default": False},
                "until": {"t": "string", "max_length": 40, "default": ""},
            },
            "default": {"enabled": False, "until": ""},
        },
        "digest_frequency": {"t": "enum", "values": ["immediate", "daily", "weekly"], "default": "immediate"},
        "browser_enabled": {"t": "bool", "default": True},
        "history": {"t": "list", "default": []},
    },
    "export": {
        "delimiter": {"t": "enum", "values": [",", ";", "|", "\t"], "default": ","},
        "encoding_with_bom": {"t": "bool", "default": False},
        "date_format": {"t": "enum", "values": ["YYYY-MM-DD", "DD-MM-YYYY", "MM/DD/YYYY"], "default": "YYYY-MM-DD"},
        "time_format": {"t": "enum", "values": ["HH:mm", "hh:mm A"], "default": "HH:mm"},
        "decimal_precision": {"t": "int", "bounds": [0, 6], "default": 2},
        "filename_pattern": {
            "t": "enum",
            "values": ["<report>_<scope>_<date>", "<report>_<date>", "<report>_<scope>"],
            "default": "<report>_<scope>_<date>",
        },
        "timezone": {"t": "string", "max_length": 40, "default": "Asia/Kolkata"},
        "default_scope": {"t": "enum", "values": ["current_term", "all", "previous_term"], "default": "current_term"},
        "templates": {"t": "list", "default": []},
    },
    "accessibility": {
        "high_contrast": {"t": "bool", "default": False},
        "color_blind_palette": {"t": "enum", "values": ["none", "protanopia", "deuteranopia", "tritanopia"], "default": "none"},
        "font_scale": {"t": "enum", "values": ["default", "large", "x-large"], "default": "default"},
        "reduced_motion": {"t": "bool", "default": False},
        "focus_ring_size": {"t": "enum", "values": ["default", "large"], "default": "default"},
        "keyboard_navigation": {"t": "bool", "default": True},
        "screen_reader_labels": {"t": "bool", "default": True},
        "preset": {"t": "enum", "values": ["none", "high_contrast", "large_text", "reduce_motion"], "default": "none"},
    },
    "personalization": {
        "recent_searches": {"t": "list", "default": []},
        "favorite_filters": {"t": "list", "default": []},
        "favorite_subjects": {"t": "list", "default": []},
        "pinned_students": {"t": "list", "default": []},
        "recent_pages": {"t": "list", "default": []},
        "quick_launch_shortcuts": {"t": "list", "default": []},
    },
    "security": {
        "password_updated_at": {"t": "string", "max_length": 40, "default": ""},
        "last_login": {"t": "string", "max_length": 40, "default": ""},
        "current_session": {
            "t": "record",
            "fields": {
                "id": {"t": "string", "max_length": 40, "default": ""},
                "started_at": {"t": "string", "max_length": 40, "default": ""},
                "ip": {"t": "string", "max_length": 64, "default": ""},
                "user_agent": {"t": "string", "max_length": 256, "default": ""},
            },
            "default": {},
        },
        "sessions": {"t": "list", "default": []},
    },
    "profile_extra": {
        "bio": {"t": "string", "max_length": 500, "default": ""},
        "office_hours": {"t": "string", "max_length": 200, "default": ""},
        "alternate_email": {"t": "string", "max_length": 254, "default": ""},
        "profile_picture": {"t": "string", "max_length": 1000, "default": ""},
    },
}


def _defaults_for(namespace: str) -> Dict[str, Any]:
    return {key: spec["default"] for key, spec in _NAMESPACE_SPECS[namespace].items()}


class SettingsService:
    """Shared Preference Engine.

    Owns the JSONB preference document: defaults, strict validation, clamping to
    admin-defined bounds, versioning, activity/audit trails, and row-scoped
    persistence via SettingsRepository.
    """

    def __init__(self, pool):
        self.repo = SettingsRepository(pool)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def default_document(self) -> Dict[str, Any]:
        return {
            "namespaces": {ns: _defaults_for(ns) for ns in _NAMESPACE_SPECS},
            "versions": {
                "schema_version": settings.PREFERENCES_SCHEMA_VERSION,
                "preference_version": 0,
                "configuration_version": 0,
                "last_modified": None,
                "last_synced": None,
                "restore_point": None,
            },
            "activity": [],
            "audit": [],
        }

    async def get_document(self, user_id: str) -> Dict[str, Any]:
        doc = self.default_document()
        stored = await self.repo.get_preferences(user_id)
        if not stored or not isinstance(stored, dict):
            return doc
        stored_namespaces = stored.get("namespaces")
        if isinstance(stored_namespaces, dict):
            for ns in _NAMESPACE_SPECS:
                stored_ns = stored_namespaces.get(ns)
                if isinstance(stored_ns, dict):
                    merged = dict(doc["namespaces"][ns])
                    for key, value in stored_ns.items():
                        if key in _NAMESPACE_SPECS[ns]:
                            merged[key] = value
                    doc["namespaces"][ns] = merged
        stored_versions = stored.get("versions")
        if isinstance(stored_versions, dict):
            for key in doc["versions"]:
                if key in stored_versions and stored_versions[key] is not None:
                    doc["versions"][key] = stored_versions[key]
        activity = stored.get("activity")
        if isinstance(activity, list):
            doc["activity"] = activity[-settings.PREFERENCES_ACTIVITY_LIMIT:]
        audit = stored.get("audit")
        if isinstance(audit, list):
            doc["audit"] = audit[-settings.PREFERENCES_AUDIT_LIMIT:]
        if doc["versions"]["schema_version"] < settings.PREFERENCES_SCHEMA_VERSION:
            doc["versions"]["schema_version"] = settings.PREFERENCES_SCHEMA_VERSION
        return doc

    def _coerce(self, fs: Dict[str, Any], value: Any) -> Tuple[Any, Optional[Dict[str, Any]], Optional[str]]:
        """Returns (coerced_value, applied_bound_entry, note)."""
        field_type = fs["t"]
        if field_type == "bool":
            if not isinstance(value, bool):
                raise PreferenceValidationError("Expected a boolean.")
            return value, None, None
        if field_type == "enum":
            if value not in fs["values"]:
                raise PreferenceValidationError(f"Expected one of {fs['values']}.")
            return value, None, None
        if field_type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise PreferenceValidationError("Expected an integer.")
            lo, hi = fs.get("bounds", (None, None))
            if lo is not None and value < lo:
                value = lo
            if hi is not None and value > hi:
                value = hi
            return value, None, None
        if field_type == "number":
            if fs.get("nullable") and value is None:
                return None, None, None
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PreferenceValidationError("Expected a number.")
            if fs.get("admin_bounds"):
                lo, hi = fs["admin_bounds"]
                original = value
                if value < lo:
                    value = lo
                elif value > hi:
                    value = hi
                if value != original:
                    note = f"Clamped to admin-defined range ({lo}–{hi})."
                    return value, {"min": lo, "max": hi, "applied": value}, note
                return value, None, None
            lo, hi = fs.get("bounds", (None, None))
            if lo is not None and value < lo:
                value = lo
            if hi is not None and value > hi:
                value = hi
            return value, None, None
        if field_type == "string":
            if not isinstance(value, str):
                raise PreferenceValidationError("Expected a string.")
            max_length = fs.get("max_length")
            return (value[:max_length] if max_length else value), None, None
        if field_type == "list":
            if not isinstance(value, list):
                raise PreferenceValidationError("Expected a list.")
            max_length = fs.get("max_length")
            return (value[:max_length] if max_length else value), None, None
        raise PreferenceValidationError("Unsupported field type.")

    def _merge_record(self, fs: Dict[str, Any], existing: Dict[str, Any], value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise PreferenceValidationError("Expected an object.")
        out = dict(existing or {})
        for key, nested in value.items():
            sub = fs["fields"].get(key)
            if sub is None:
                raise PreferenceValidationError(f"Unknown field '{key}'.")
            if sub["t"] == "record":
                base = existing.get(key) if isinstance(existing, dict) else {}
                if not isinstance(base, dict):
                    base = {}
                out[key] = self._merge_record(sub, base, nested)
            else:
                out[key] = self._coerce(sub, nested)[0]
        return out

    def _validate_and_merge(
        self, namespace: str, existing: Dict[str, Any], patch: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        spec = _NAMESPACE_SPECS[namespace]
        auto_managed = _AUTO_MANAGED.get(namespace, set())
        merged = dict(existing)
        applied_bounds: Dict[str, Any] = {}
        notes: List[str] = []
        for key, value in patch.items():
            if key not in spec:
                raise PreferenceValidationError(f"Unknown field '{key}' in '{namespace}' preferences.")
            if key in auto_managed:
                raise PreferenceValidationError(f"Field '{key}' is managed by the system.")
            fs = spec[key]
            try:
                if fs["t"] == "record":
                    base = merged.get(key)
                    if not isinstance(base, dict):
                        base = {}
                    coerced = self._merge_record(fs, base, value)
                    applied_entry = None
                else:
                    coerced, applied_entry, _ = self._coerce(fs, value)
            except PreferenceValidationError as exc:
                raise PreferenceValidationError(f"Field '{key}': {exc}") from exc
            if applied_entry:
                applied_bounds[key] = applied_entry
                notes.append(f"Field '{key}': clamped to admin-defined range ({applied_entry['min']}–{applied_entry['max']}).")
            merged[key] = coerced
        return merged, applied_bounds, notes

    async def update_namespace(
        self, user_id: str, namespace: str, patch: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        if namespace not in _NAMESPACE_SPECS:
            raise PreferenceValidationError(f"Unknown preference namespace '{namespace}'.")
        doc = await self.get_document(user_id)
        existing = doc["namespaces"][namespace]
        merged, applied_bounds, notes = self._validate_and_merge(namespace, existing, patch)
        if applied_bounds:
            current_bounds = doc["namespaces"]["analytics"].get("applied_bounds")
            if not isinstance(current_bounds, dict):
                current_bounds = {}
            merged["applied_bounds"] = {**current_bounds, **applied_bounds}
        now = self._now()
        versions = doc["versions"]
        versions["preference_version"] = int(versions.get("preference_version") or 0) + 1
        if namespace in _CONFIGURATION_NAMESPACES:
            versions["configuration_version"] = int(versions.get("configuration_version") or 0) + 1
        versions["last_modified"] = now
        activity = doc["activity"]
        activity.append(
            {"event": "preference_change", "at": now, "namespace": namespace, "detail": f"{namespace} updated"}
        )
        doc["activity"] = activity[-settings.PREFERENCES_ACTIVITY_LIMIT:]
        audit = doc["audit"]
        audit.append(
            {"action": "update", "at": now, "namespace": namespace, "summary": f"Updated {len(patch)} field(s)."}
        )
        doc["audit"] = audit[-settings.PREFERENCES_AUDIT_LIMIT:]
        doc["namespaces"][namespace] = merged
        persisted = await self.repo.update_preferences(user_id, doc)
        highlights = [f"{namespace} preferences updated."]
        highlights.extend(notes)
        return persisted, highlights

    @staticmethod
    def _snapshot(doc: Dict[str, Any]) -> Dict[str, Any]:
        """A named, timestamped snapshot of the current namespaces (restore point)."""
        return {
            "created_at": SettingsService._now(),
            "namespaces": copy.deepcopy(doc["namespaces"]),
        }

    async def _persist(
        self,
        user_id: str,
        doc: Dict[str, Any],
        *,
        namespace: str,
        action: str,
        summary: str,
        bump_configuration: bool,
        event: str = "preference_change",
        detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bump versions, append activity/audit, trim, and persist the document."""
        now = self._now()
        versions = doc["versions"]
        versions["preference_version"] = int(versions.get("preference_version") or 0) + 1
        if bump_configuration:
            versions["configuration_version"] = int(versions.get("configuration_version") or 0) + 1
        versions["last_modified"] = now
        activity = doc["activity"]
        activity.append(
            {"event": event, "at": now, "namespace": namespace, "detail": detail or f"{namespace} updated"}
        )
        doc["activity"] = activity[-settings.PREFERENCES_ACTIVITY_LIMIT:]
        audit = doc["audit"]
        audit.append({"action": action, "at": now, "namespace": namespace, "summary": summary})
        doc["audit"] = audit[-settings.PREFERENCES_AUDIT_LIMIT:]
        return await self.repo.update_preferences(user_id, doc)

    async def reset_namespace(
        self,
        user_id: str,
        level: str,
        include_profile_extra: bool = False,
    ) -> Tuple[Dict[str, Any], List[str]]:
        if level not in _RESET_LEVELS:
            raise PreferenceValidationError(f"Unknown reset level '{level}'.")
        doc = await self.get_document(user_id)
        targets = _RESET_LEVELS[level]
        if targets is None:
            targets = list(_NAMESPACE_SPECS.keys())
            if not include_profile_extra:
                targets.remove("profile_extra")
        for ns in targets:
            if ns not in _NAMESPACE_SPECS:
                raise PreferenceValidationError(f"Unknown preference namespace '{ns}'.")
        doc["versions"]["restore_point"] = self._snapshot(doc)
        for ns in targets:
            doc["namespaces"][ns] = _defaults_for(ns)
        bump_configuration = any(ns in _CONFIGURATION_NAMESPACES for ns in targets)
        label = "factory" if level == "factory" else ", ".join(targets)
        persisted = await self._persist(
            user_id,
            doc,
            namespace=label,
            action="reset",
            summary=f"Reset '{level}': {len(targets)} namespace(s) restored to defaults.",
            bump_configuration=bump_configuration,
            detail=f"'{level}' reset applied.",
        )
        highlights = [
            (
                "Factory reset applied to all preference namespaces."
                if level == "factory"
                else f"Reset applied to {label}."
            ),
            "A restore point was created before resetting — you can restore your previous configuration.",
        ]
        return persisted, highlights

    async def backup_workspace(self, user_id: str) -> Dict[str, Any]:
        """Preference-only configuration backup. Never includes academic or identity data."""
        doc = await self.get_document(user_id)
        return {
            "schema_version": doc["versions"]["schema_version"],
            "preference_version": doc["versions"]["preference_version"],
            "configuration_version": doc["versions"]["configuration_version"],
            "exported_at": self._now(),
            "namespaces": {ns: copy.deepcopy(doc["namespaces"][ns]) for ns in _BACKUP_NAMESPACES},
        }

    async def import_workspace(self, user_id: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        if not isinstance(payload, dict):
            raise PreferenceValidationError("Backup must be a JSON object.")
        for ns, values in payload.items():
            if ns not in _BACKUP_NAMESPACES:
                raise PreferenceValidationError(f"Backup contains unsupported namespace '{ns}'.")
            if not isinstance(values, dict):
                raise PreferenceValidationError(f"Backup namespace '{ns}' must be an object.")
        validated: Dict[str, Any] = {}
        for ns in _BACKUP_NAMESPACES:
            if ns not in payload:
                continue
            spec = _NAMESPACE_SPECS[ns]
            merged = dict(_defaults_for(ns))
            for key, value in payload[ns].items():
                if key not in spec:
                    raise PreferenceValidationError(f"Unknown field '{key}' in '{ns}'.")
                if key in _AUTO_MANAGED.get(ns, set()):
                    continue
                fs = spec[key]
                try:
                    if fs["t"] == "record":
                        merged[key] = self._merge_record(fs, {}, value)
                    else:
                        merged[key] = self._coerce(fs, value)[0]
                except PreferenceValidationError as exc:
                    raise PreferenceValidationError(f"Field '{key}': {exc}") from exc
            validated[ns] = merged
        if not validated:
            raise PreferenceValidationError("Backup has no preference namespaces to import.")
        doc = await self.get_document(user_id)
        doc["versions"]["restore_point"] = self._snapshot(doc)
        for ns, values in validated.items():
            doc["namespaces"][ns] = values
        persisted = await self._persist(
            user_id,
            doc,
            namespace="import",
            action="import",
            summary=f"Imported {len(validated)} namespace(s) from a configuration backup.",
            bump_configuration=True,
            detail="workspace configuration imported.",
        )
        return persisted, [
            f"Workspace configuration imported ({len(validated)} namespaces).",
            "A restore point was created before importing.",
        ]

    async def restore_workspace(self, user_id: str) -> Tuple[Dict[str, Any], List[str]]:
        doc = await self.get_document(user_id)
        restore_point = doc["versions"].get("restore_point")
        if not isinstance(restore_point, dict) or not isinstance(restore_point.get("namespaces"), dict):
            raise PreferenceValidationError("No restore point available.")
        snapshot = copy.deepcopy(restore_point["namespaces"])
        for ns in _NAMESPACE_SPECS:
            if ns in snapshot and isinstance(snapshot[ns], dict):
                doc["namespaces"][ns] = snapshot[ns]
        doc["versions"]["restore_point"] = None
        persisted = await self._persist(
            user_id,
            doc,
            namespace="restore",
            action="restore",
            summary="Restored preferences from the previous restore point.",
            bump_configuration=True,
            detail="workspace restored from restore point.",
        )
        return persisted, ["Workspace restored to the previous restore point."]
