"""Support for Bond Pro scenes (/v2/scenes)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .entity import BondHubEntity
from .models import BondData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one scene entity per Bond scene."""
    data = entry.runtime_data
    async_add_entities(
        BondScene(data, scene_id, scene)
        for scene_id, scene in data.hub.scenes.items()
    )


class BondScene(BondHubEntity, Scene):
    """A scene stored on the bridge; each actor runs individually."""

    def __init__(self, data: BondData, scene_id: str, scene: dict[str, Any]) -> None:
        """Initialize the scene."""
        super().__init__(data, f"scene_{scene_id}")
        self._scene_id = scene_id
        self._attr_name = scene.get("name") or scene_id
        # Imported scenes (e.g. PowerView) are opaque and carry no actors.
        self._attr_extra_state_attributes = {
            key: scene[key]
            for key in ("actors", "types", "locations", "imported_from")
            if key in scene
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Run the scene."""
        await self._bond.run_scene(self._scene_id)
