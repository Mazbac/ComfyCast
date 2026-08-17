from __future__ import annotations

from dataclasses import asdict, dataclass
import ipaddress
import os
import threading
import time


@dataclass(frozen=True)
class CastDevice:
    name: str
    host: str
    model: str
    uuid: str
    cast_type: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class DiscoveryError(RuntimeError):
    pass


def _load_pychromecast():
    try:
        import pychromecast
    except ImportError as exc:
        raise DiscoveryError(
            "PyChromecast is not installed. Install ComfyCast requirements and restart ComfyUI."
        ) from exc
    return pychromecast


def configured_known_hosts() -> list[str]:
    raw = os.getenv("COMFYCAST_KNOWN_HOSTS", "")
    hosts: list[str] = []
    for value in raw.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise DiscoveryError(
                f"COMFYCAST_KNOWN_HOSTS contains an invalid IP address: {value}"
            ) from exc
        hosts.append(value)
    return hosts


def discover_video_devices(
    timeout: float = 5.0,
    known_hosts: list[str] | None = None,
) -> list[CastDevice]:
    pychromecast = _load_pychromecast()
    browser = None
    if known_hosts is None:
        known_hosts = configured_known_hosts() or None

    try:
        casts, browser = pychromecast.get_chromecasts(
            timeout=timeout,
            known_hosts=known_hosts,
        )
        devices: list[CastDevice] = []
        for cast in casts:
            if cast.cast_type != "cast":
                continue
            info = cast.cast_info
            devices.append(
                CastDevice(
                    name=cast.name or info.friendly_name or str(cast.uuid),
                    host=info.host,
                    model=cast.model_name or info.model_name or "Unknown",
                    uuid=str(cast.uuid),
                    cast_type=cast.cast_type or "cast",
                )
            )
        return sorted(devices, key=lambda item: item.name.casefold())
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(f"Chromecast discovery failed: {exc}") from exc
    finally:
        if browser is not None:
            pychromecast.discovery.stop_discovery(browser)


class DiscoveryService:
    def __init__(self, ttl_seconds: float = 15.0):
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._devices: list[CastDevice] = []
        self._updated_at = 0.0

    def list_devices(self, force: bool = False) -> list[CastDevice]:
        with self._lock:
            stale = time.monotonic() - self._updated_at >= self._ttl
            if force or stale or not self._devices:
                self._devices = discover_video_devices()
                self._updated_at = time.monotonic()
            return list(self._devices)

    @staticmethod
    def _find(devices: list[CastDevice], value: str) -> CastDevice | None:
        for device in devices:
            if value in {
                device.name.casefold(),
                device.host.casefold(),
                device.uuid.casefold(),
            }:
                return device
        return None

    def resolve(self, identifier: str) -> CastDevice:
        value = identifier.strip().casefold()
        if not value:
            raise DiscoveryError("No Chromecast device selected.")

        with self._lock:
            cached = list(self._devices)
        match = self._find(cached, value)
        if match is not None:
            return match

        devices = self.list_devices(force=True)
        match = self._find(devices, value)
        if match is not None:
            return match

        try:
            ipaddress.ip_address(identifier.strip())
        except ValueError:
            pass
        else:
            direct = discover_video_devices(
                timeout=5.0,
                known_hosts=[identifier.strip()],
            )
            match = self._find(direct, value)
            if match is not None:
                return match

        raise DiscoveryError(f"Cast device not found: {identifier}")


DISCOVERY = DiscoveryService()
