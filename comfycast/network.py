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
    return (
        address.version == 4
        and not address.is_loopback
        and not address.is_unspecified
        and not address.is_multicast
        and not address.is_link_local
    )


def _common_prefix_bits(left: str, right: str) -> int:
    a = int(ipaddress.IPv4Address(left))
    b = int(ipaddress.IPv4Address(right))
    xor = a ^ b
    return 32 if xor == 0 else 32 - xor.bit_length()


def _local_ipv4_candidates() -> list[str]:
    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        return []
    return [value for value in addresses if _is_lan_ipv4(value)]


def get_lan_ip(target_host: str | None = None) -> str:
    override = os.getenv("COMFYCAST_HOST_IP", "").strip()
    if override:
        if not _is_lan_ipv4(override):
            raise NetworkError(
                f"COMFYCAST_HOST_IP is not a usable IPv4 address: {override}"
            )
        return override

    candidates = _local_ipv4_candidates()
    if target_host and _is_lan_ipv4(target_host) and candidates:
        # Prefer the local address sharing the longest network prefix with the
        # receiver. This avoids advertising VPN/Tailscale addresses to a LAN TV.
        return max(
            candidates,
            key=lambda value: _common_prefix_bits(value, target_host),
        )

    # Fallback to the interface used for normal outbound traffic.
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

    if candidates:
        return candidates[0]

    raise NetworkError(
        "Could not determine a LAN IPv4 address. Set COMFYCAST_HOST_IP to "
        "the PC address reachable by Chromecast."
    )
