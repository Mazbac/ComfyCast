from __future__ import annotations

from dataclasses import asdict, dataclass
import ipaddress
import os
import threading
import time


@dataclass(frozen=True, slots=True)
class CastDevice:
    name: str
    host: str
    port: int
    model: str
    uuid: str
    cast_type: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class DiscoveryError(RuntimeError):
    pass


def _load_pychromecast():
    try:
        import pychromecast
    except ImportError as exc:
        raise DiscoveryError(
            "PyChromecast is not installed. Install ComfyCast requirements "
            "and restart ComfyUI."
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
                    port=int(info.port or 8009),
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
        self._state_lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._devices: tuple[CastDevice, ...] = ()
        self._index: dict[str, CastDevice] = {}
        self._updated_at = 0.0

    @staticmethod
    def _build_index(devices: tuple[CastDevice, ...]) -> dict[str, CastDevice]:
        index: dict[str, CastDevice] = {}
        for device in devices:
            for key in (device.uuid, device.host, device.name):
                index.setdefault(key.casefold(), device)
        return index

    def _remember(self, device: CastDevice) -> None:
        with self._state_lock:
            for key in (device.uuid, device.host, device.name):
                self._index[key.casefold()] = device

    def _cached(self, value: str) -> CastDevice | None:
        with self._state_lock:
            return self._index.get(value.casefold())

    def _snapshot(self) -> tuple[tuple[CastDevice, ...], float]:
        with self._state_lock:
            return self._devices, self._updated_at

    def list_devices(self, force: bool = False) -> list[CastDevice]:
        requested_at = time.monotonic()
        devices, updated_at = self._snapshot()
        fresh = bool(devices) and requested_at - updated_at < self._ttl
        if fresh and not force:
            return list(devices)

        # Only one network scan may run at a time. A second force-refresh that
        # was already waiting reuses the scan that completed while it waited.
        with self._refresh_lock:
            devices, updated_at = self._snapshot()
            if updated_at >= requested_at:
                return list(devices)
            if devices and not force and time.monotonic() - updated_at < self._ttl:
                return list(devices)

            refreshed = tuple(discover_video_devices())
            with self._state_lock:
                self._devices = refreshed
                self._index = self._build_index(refreshed)
                self._updated_at = time.monotonic()
            return list(refreshed)

    def resolve(self, identifier: str) -> CastDevice:
        raw = identifier.strip()
        if not raw:
            raise DiscoveryError("No Chromecast device selected.")

        match = self._cached(raw)
        if match is not None:
            return match

        # An explicit IP can be resolved without waiting for a full mDNS scan.
        try:
            ipaddress.ip_address(raw)
        except ValueError:
            pass
        else:
            direct = discover_video_devices(timeout=5.0, known_hosts=[raw])
            for device in direct:
                if raw.casefold() in {
                    device.host.casefold(),
                    device.uuid.casefold(),
                    device.name.casefold(),
                }:
                    self._remember(device)
                    return device
            raise DiscoveryError(f"Cast device not found: {identifier}")

        self.list_devices(force=True)
        match = self._cached(raw)
        if match is not None:
            return match

        raise DiscoveryError(f"Cast device not found: {identifier}")


DISCOVERY = DiscoveryService()
