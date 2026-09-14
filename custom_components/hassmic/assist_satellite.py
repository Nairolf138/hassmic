"""Assist satellite platform adapter for HassMic.

Kept out of const.PLATFORMS until the Android playback bridge is enabled.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .native_satellite import HassMicNativeSatellite


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Prepare the native satellite entity without enabling it yet."""
    satellite = HassMicNativeSatellite(hass, config_entry)
    async_add_entities([satellite])
