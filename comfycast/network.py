from __future__ import annotations

import ipaddress
import os
import socket


class NetworkError(RuntimeError):
    pass


def _is_lan_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and not address.is_loopback and not address.is_unspecified


def get_lan_ip() -> str:
    override = os.getenv("COMFYCAST_HOST_IP", "").strip()
    if override:
        if not _is_lan_ipv4(override):
            raise NetworkError(f"COMFYCAST_HOST_IP is not a usable IPv4 address: {override}")
        return override

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        candidate = probe.getsockname()[0]
        if _is_lan_ipv4(candidate):
            return candidate
    except OSError:
        pass
    finally:
        probe.close()

    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        addresses = []

    for candidate in addresses:
        if _is_lan_ipv4(candidate):
            return candidate

    raise NetworkError(
        "Could not determine a LAN IPv4 address. Set COMFYCAST_HOST_IP to the PC address reachable by Chromecast."
    )
