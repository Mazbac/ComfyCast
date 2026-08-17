from __future__ import annotations

import time

from .discovery import DISCOVERY, DiscoveryError, _load_pychromecast


class CastError(RuntimeError):
    pass


def _wait_for_media(cast, media_url: str, timeout: float = 10.0) -> str:
    controller = cast.media_controller
    deadline = time.monotonic() + timeout
    accepted_states = {"PLAYING", "PAUSED", "BUFFERING"}

    while time.monotonic() < deadline:
        status = controller.status
        if status.content_id == media_url and status.player_state in accepted_states:
            return status.player_state
        try:
            controller.update_status()
        except Exception:
            pass
        time.sleep(0.25)

    status = controller.status
    raise CastError(
        "Receiver did not confirm the ComfyCast media URL "
        f"(state={status.player_state}, content={status.content_id!r})."
    )


def cast_media(
    device_identifier: str,
    media_url: str,
    content_type: str,
    *,
    title: str | None = None,
    autoplay: bool = True,
) -> dict[str, str]:
    pychromecast = _load_pychromecast()
    try:
        device = DISCOVERY.resolve(device_identifier)
    except DiscoveryError as exc:
        raise CastError(str(exc)) from exc

    browser = None
    cast = None
    try:
        casts, browser = pychromecast.get_chromecasts(
            timeout=5,
            known_hosts=[device.host],
        )
        for candidate in casts:
            info = candidate.cast_info
            if str(candidate.uuid) == device.uuid or info.host == device.host:
                cast = candidate
                break
        if cast is None:
            raise CastError(f"Could not connect to Cast device: {device.name}")

        cast.wait(timeout=10)
        from pychromecast.quick_play import quick_play

        quick_play(
            cast,
            "default_media_receiver",
            {
                "media_id": media_url,
                "media_type": content_type,
                "title": title or "ComfyCast",
                "autoplay": autoplay,
                "stream_type": "BUFFERED",
            },
            timeout=15,
        )
        player_state = _wait_for_media(cast, media_url, timeout=10)
        return {
            "name": device.name,
            "host": device.host,
            "model": device.model,
            "uuid": device.uuid,
            "player_state": player_state,
        }
    except CastError:
        raise
    except Exception as exc:
        raise CastError(f"Casting to {device.name} failed: {exc}") from exc
    finally:
        if browser is not None:
            try:
                pychromecast.discovery.stop_discovery(browser)
            except Exception:
                pass
        if cast is not None:
            try:
                cast.disconnect(timeout=2)
            except Exception:
                pass
