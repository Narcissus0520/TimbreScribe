"""Optional, gated MuScriptor integration without eager model imports."""

from timbrescribe.infrastructure.muscriptor.acceptance import JsonModelAcceptanceStore
from timbrescribe.infrastructure.muscriptor.config import validate_muscriptor_config
from timbrescribe.infrastructure.muscriptor.credentials import KeyringCredentialStore
from timbrescribe.infrastructure.muscriptor.manager import (
    MuscriptorModelManager,
    MuscriptorModelStatus,
)
from timbrescribe.infrastructure.muscriptor.manifest import (
    MuscriptorCatalog,
    load_muscriptor_catalog,
)
from timbrescribe.infrastructure.muscriptor.resources import (
    ResourcePreflight,
    ResourceSnapshot,
    inspect_resources,
    preflight_resources,
)

__all__ = [
    "JsonModelAcceptanceStore",
    "KeyringCredentialStore",
    "MuscriptorCatalog",
    "MuscriptorModelManager",
    "MuscriptorModelStatus",
    "ResourcePreflight",
    "ResourceSnapshot",
    "inspect_resources",
    "load_muscriptor_catalog",
    "preflight_resources",
    "validate_muscriptor_config",
]
