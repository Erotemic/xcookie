"""Provider-neutral publishing policy helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SUPPORTED_TRUSTED_PUBLISHING_PROVIDERS = frozenset({'github', 'gitlab'})


def trusted_publishing_providers(config: Mapping[str, Any]) -> frozenset[str]:
    """Resolve the CI providers that should use PyPI Trusted Publishing.

    ``ci_pypi_trusted_publishing`` historically was a boolean and only
    affected GitHub Actions.  Preserve that contract for compatibility:
    ``True`` means GitHub only, while a provider collection opts into the
    corresponding providers explicitly.  ``"all"`` is accepted as a compact
    spelling for every provider xcookie currently knows how to render.
    """
    value = config.get('ci_pypi_trusted_publishing', False)

    if value is None or value is False:
        return frozenset()
    if value is True:
        # Backward compatibility: before GitLab support landed this switch
        # meant "use GitHub Trusted Publishing" and had no GitLab effect.
        return frozenset({'github'})

    if isinstance(value, str):
        text = value.strip().lower()
        if text in {'', 'false', 'no', 'none', 'off', '0'}:
            return frozenset()
        if text in {'true', 'yes', 'on', '1'}:
            return frozenset({'github'})
        if text in {'all', '*'}:
            return SUPPORTED_TRUSTED_PUBLISHING_PROVIDERS
        providers = {
            part.strip().lower()
            for part in text.replace(',', ' ').split()
            if part.strip()
        }
    elif isinstance(value, Mapping):
        providers = {
            str(provider).strip().lower()
            for provider, enabled in value.items()
            if enabled
        }
    elif isinstance(value, Sequence):
        providers = {
            str(provider).strip().lower()
            for provider in value
            if str(provider).strip()
        }
    else:
        raise TypeError(
            'ci_pypi_trusted_publishing must be a bool, provider name, '
            f'provider collection, or mapping; got {type(value)!r}'
        )

    unknown = providers - SUPPORTED_TRUSTED_PUBLISHING_PROVIDERS
    if unknown:
        raise ValueError(
            'Unknown ci_pypi_trusted_publishing provider(s): '
            f'{sorted(unknown)!r}. Supported providers are '
            f'{sorted(SUPPORTED_TRUSTED_PUBLISHING_PROVIDERS)!r}.'
        )
    return frozenset(providers)


def trusted_publishing_enabled(
    config: Mapping[str, Any], provider: str
) -> bool:
    """Return whether ``provider`` should use PyPI Trusted Publishing."""
    provider = provider.strip().lower()
    if provider not in SUPPORTED_TRUSTED_PUBLISHING_PROVIDERS:
        raise KeyError(provider)
    return provider in trusted_publishing_providers(config)
