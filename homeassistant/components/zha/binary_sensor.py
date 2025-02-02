"""Binary sensors on Zigbee Home Automation networks."""
from __future__ import annotations

import functools

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CHANNEL_ACCELEROMETER,
    CHANNEL_BINARY_INPUT,
    CHANNEL_OCCUPANCY,
    CHANNEL_ON_OFF,
    CHANNEL_ZONE,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

# Zigbee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000D: BinarySensorDeviceClass.MOTION,
    0x0015: BinarySensorDeviceClass.OPENING,
    0x0028: BinarySensorDeviceClass.SMOKE,
    0x002A: BinarySensorDeviceClass.MOISTURE,
    0x002B: BinarySensorDeviceClass.GAS,
    0x002D: BinarySensorDeviceClass.VIBRATION,
}

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.BINARY_SENSOR)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.BINARY_SENSOR)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.BINARY_SENSOR
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation binary sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.BINARY_SENSOR]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class BinarySensor(ZhaEntity, BinarySensorEntity):
    """ZHA BinarySensor."""

    SENSOR_ATTR: str | None = None

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel = channels[0]

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on based on the state machine."""
        raw_state = self._channel.cluster.get(self.SENSOR_ATTR)
        if raw_state is None:
            return False
        return self.parse(raw_state)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        self.async_write_ha_state()

    @staticmethod
    def parse(value: bool | int) -> bool:
        """Parse the raw attribute into a bool state."""
        return bool(value)


@MULTI_MATCH(channel_names=CHANNEL_ACCELEROMETER)
class Accelerometer(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "acceleration"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.MOVING


@MULTI_MATCH(channel_names=CHANNEL_OCCUPANCY)
class Occupancy(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "occupancy"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.OCCUPANCY


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Opening(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "on_off"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.OPENING


@MULTI_MATCH(channel_names=CHANNEL_BINARY_INPUT)
class BinaryInput(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "present_value"


@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    manufacturers="IKEA of Sweden",
    models=lambda model: isinstance(model, str)
    and model is not None
    and model.find("motion") != -1,
)
@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    manufacturers="Philips",
    models={"SML001", "SML002"},
)
class Motion(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "on_off"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.MOTION


@MULTI_MATCH(channel_names=CHANNEL_ZONE)
class IASZone(BinarySensor):
    """ZHA IAS BinarySensor."""

    SENSOR_ATTR = "zone_status"

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return device class from component DEVICE_CLASSES."""
        return CLASS_MAPPING.get(self._channel.cluster.get("zone_type"))

    @staticmethod
    def parse(value: bool | int) -> bool:
        """Parse the raw attribute into a bool state."""
        return BinarySensor.parse(value & 3)  # use only bit 0 and 1 for alarm state


@MULTI_MATCH(
    channel_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
class FrostLock(BinarySensor, id_suffix="frost_lock"):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "frost_lock"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.LOCK


@MULTI_MATCH(channel_names="ikea_airpurifier")
class ReplaceFilter(BinarySensor, id_suffix="replace_filter"):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "replace_filter"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM


@MULTI_MATCH(channel_names="opple_cluster", models={"aqara.feeder.acn001"})
class AqaraPetFeederErrorDetected(BinarySensor, id_suffix="error_detected"):
    """ZHA aqara pet feeder error detected binary sensor."""

    SENSOR_ATTR = "error_detected"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    _attr_name: str = "Error detected"


@MULTI_MATCH(
    channel_names="opple_cluster", models={"lumi.plug.mmeu01", "lumi.plug.maeu01"}
)
class XiaomiPlugConsumerConnected(BinarySensor, id_suffix="consumer_connected"):
    """ZHA Xiaomi plug consumer connected binary sensor."""

    SENSOR_ATTR = "consumer_connected"
    _attr_name: str = "Consumer connected"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PLUG


@MULTI_MATCH(channel_names="opple_cluster", models={"lumi.airrtc.agl001"})
class AqaraThermostatWindowOpen(BinarySensor, id_suffix="window_open"):
    """ZHA Aqara thermostat window open binary sensor."""

    SENSOR_ATTR = "window_open"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.WINDOW
    _attr_name: str = "Window open"


@MULTI_MATCH(channel_names="opple_cluster", models={"lumi.airrtc.agl001"})
class AqaraThermostatValveAlarm(BinarySensor, id_suffix="valve_alarm"):
    """ZHA Aqara thermostat valve alarm binary sensor."""

    SENSOR_ATTR = "valve_alarm"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    _attr_name: str = "Valve alarm"


@CONFIG_DIAGNOSTIC_MATCH(channel_names="opple_cluster", models={"lumi.airrtc.agl001"})
class AqaraThermostatCalibrated(BinarySensor, id_suffix="calibrated"):
    """ZHA Aqara thermostat calibrated binary sensor."""

    SENSOR_ATTR = "calibrated"
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_name: str = "Calibrated"


@CONFIG_DIAGNOSTIC_MATCH(channel_names="opple_cluster", models={"lumi.airrtc.agl001"})
class AqaraThermostatExternalSensor(BinarySensor, id_suffix="sensor"):
    """ZHA Aqara thermostat external sensor binary sensor."""

    SENSOR_ATTR = "sensor"
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_name: str = "External sensor"


@MULTI_MATCH(channel_names="opple_cluster", models={"lumi.sensor_smoke.acn03"})
class AqaraLinkageAlarmState(BinarySensor, id_suffix="linkage_alarm_state"):
    """ZHA Aqara linkage alarm state binary sensor."""

    SENSOR_ATTR = "linkage_alarm_state"
    _attr_name: str = "Linkage alarm state"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.SMOKE
