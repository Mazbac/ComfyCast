from __future__ import annotations

import asyncio

from aiohttp import web
from server import PromptServer

from .comfycast.discovery import DISCOVERY, DiscoveryError
from .comfycast.media_server import MEDIA_SERVER
from .comfycast.network import NetworkError, get_lan_ip


@PromptServer.instance.routes.get("/comfycast/devices")
async def comfycast_devices(request: web.Request) -> web.Response:
    force = request.query.get("refresh", "0") in {"1", "true", "yes"}
    try:
        devices = await asyncio.to_thread(DISCOVERY.list_devices, force)
    except DiscoveryError as exc:
        return web.json_response(
            {"ok": False, "error": str(exc), "devices": []},
            status=503,
        )

    return web.json_response(
        {
            "ok": True,
            "devices": [device.to_dict() for device in devices],
        }
    )


@PromptServer.instance.routes.get("/comfycast/status")
async def comfycast_status(_request: web.Request) -> web.Response:
    try:
        host = get_lan_ip()
    except NetworkError as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=503)

    return web.json_response(
        {
            "ok": True,
            "host": host,
            "media_server_started": MEDIA_SERVER.is_running,
            "media_server_port": MEDIA_SERVER.current_port,
        }
    )
