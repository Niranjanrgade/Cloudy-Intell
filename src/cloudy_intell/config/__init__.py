"""Configuration package for Cloudy-Intell.

Exports application settings (``AppSettings``, ``get_settings``) and provider
metadata (``ProviderMeta``, ``AWS_META``, ``AZURE_META``, ``DOMAINS``) used
throughout the application to drive provider-specific behavior.
"""

from .provider_meta import AZURE_META, AWS_META, DOMAINS, ProviderMeta, ProviderName, get_provider_meta
from .settings import AppSettings, get_settings

__all__ = [
    "AppSettings",
    "get_settings",
    "ProviderMeta",
    "ProviderName",
    "AWS_META",
    "AZURE_META",
    "DOMAINS",
    "get_provider_meta",
]
