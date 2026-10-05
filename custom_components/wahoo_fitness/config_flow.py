"""Validated manual setup and Home Assistant's shared Zeroconf discovery."""

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from wftnp import Endpoint, WftnpClient, WftnpError

from .const import DEFAULT_PORT, DOMAIN
from .device import Device, UnsupportedDevice, inspect_device


async def probe(host: str, port: int) -> Device:
    client = WftnpClient(Endpoint(host, port), auto_reconnect=False)
    try:
        async with asyncio.timeout(30):
            await client.start()
            await client.wait_ready(timeout=10)
            return await inspect_device(client)
    finally:
        await client.stop()


class WahooConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _discovered: dict[str, Any]
    _device: Device
    _title: str

    async def _validate(self, data: dict[str, Any]) -> Device:
        device = await probe(data[CONF_HOST], data[CONF_PORT])
        await self.async_set_unique_id(device.serial)
        if self.source == config_entries.SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch()
        else:
            self._abort_if_unique_id_configured(updates=data)
        return device

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._form("user", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._form("reconfigure", user_input)

    async def _form(self, step: str, data: dict[str, Any] | None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if data is not None:
            data = {CONF_HOST: data[CONF_HOST].strip(), CONF_PORT: data[CONF_PORT]}
            try:
                device = await self._validate(data)
            except WftnpError, TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except UnsupportedDevice, ValueError:
                errors["base"] = "unsupported_device"
            else:
                if step == "reconfigure":
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=data
                    )
                return self.async_create_entry(title=f"Wahoo {device.model}", data=data)
        defaults = data or (dict(self._get_reconfigure_entry().data) if step == "reconfigure" else {})
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        self._discovered = {CONF_HOST: discovery_info.host, CONF_PORT: discovery_info.port or DEFAULT_PORT}
        self._title = discovery_info.name.removesuffix("._wahoo-fitness-tnp._tcp.local.")
        self.context["title_placeholders"] = {"name": self._title}
        try:
            self._device = await self._validate(self._discovered)
        except WftnpError, TimeoutError, OSError:
            return self.async_abort(reason="cannot_connect")
        except UnsupportedDevice:
            return self.async_abort(reason="unsupported_device")
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=self._title, data=self._discovered)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm", description_placeholders={"name": self._title}
        )
