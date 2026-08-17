from __future__ import annotations

from pathlib import Path
import logging
import time
from uuid import UUID

from .discovery import CastDevice, DISCOVERY, DiscoveryError, _load_pychromecast
from .media_server import MEDIA_SERVER


DEFAULT_MEDIA_TTL_SECONDS = 60 * 60
LOOP_MEDIA_TTL_SECONDS = 24 * 60 * 60
LOGGER = logging.getLogger(__name__)


class CastError(RuntimeError):
    pass


def _build_load_message(
    media_url: str,
    content_type: str,
    *,
    title: str | None,
    autoplay: bool,
    loop: bool,
) -> dict:
    media = {
        "contentId": media_url,
        "streamType": "BUFFERED",
        "contentType": content_type,
        "metadata": {
            "metadataType": 0,
            "title": title or "ComfyCast",
        },
    }
    message = {
        "type": "LOAD",
        "media": media,
        "autoplay": autoplay,
        "customData": {},
    }
    if loop:
        message["queueData"] = {
            "repeatMode": "REPEAT_SINGLE",
            "items": [
                {
                    "media": media,
                    "autoplay": True,
                    "startTime": 0,
                    "preloadTime": 0,
                }
            ],
            "startIndex": 0,
            "startTime": 0,
        }
    return message


def _wait_for_media(cast, media_url: str, timeout: float = 10.0) -> str:
    controller = cast.media_controller
    deadline = time.monotonic() + timeout
    next_refresh = 0.0
    accepted_states = {"PLAYING", "PAUSED", "BUFFERING"}

    while True:
        status = controller.status
        if status.content_id == media_url and status.player_state in accepted_states:
            return status.player_state
        now = time.monotonic()
        if now >= deadline:
            break
        if now >= next_refresh:
            try:
                controller.update_status()
            except Exception:
                pass
            next_refresh = now + 0.5
        time.sleep(min(0.1, max(0.0, deadline - now)))

    status = controller.status
    raise CastError(
        "Receiver did not start ComfyCast media "
        f"(state={status.player_state}, idle_reason={status.idle_reason!r}, "
        f"session={status.media_session_id!r}, duration={status.duration!r}, "
        f"content={status.content_id!r})."
    )


def _connect_direct(pychromecast, device: CastDevice):
    return pychromecast.get_chromecast_from_host(
        (
            device.host,
            device.port,
            UUID(device.uuid),
            device.model,
            device.name,
        ),
        tries=2,
        retry_wait=0.25,
        timeout=5,
    )


def _send_load(
    cast,
    media_url: str,
    content_type: str,
    *,
    title: str | None,
    autoplay: bool,
    loop: bool,
    timeout: float = 15.0,
) -> None:
    from pychromecast.quick_play import DefaultMediaReceiverController
    from pychromecast.response_handler import WaitResponse

    controller = DefaultMediaReceiverController()
    cast.register_handler(controller)
    try:
        response = WaitResponse(timeout, f"load {media_url}")
        controller.send_message(
            _build_load_message(
                media_url,
                content_type,
                title=title,
                autoplay=autoplay,
                loop=loop,
            ),
            inc_session_id=True,
            callback_function=response.callback,
        )
        response.wait_response()
    finally:
        cast.unregister_handler(controller)


def _load_with_retry(
    cast,
    media_url: str,
    content_type: str,
    *,
    title: str | None,
    autoplay: bool,
    loop: bool,
) -> str:
    last_error: Exception | None = None
    for attempt, wait_timeout in enumerate((10.0, 15.0), start=1):
        try:
            _send_load(
                cast,
                media_url,
                content_type,
                title=title,
                autoplay=autoplay,
                loop=loop,
            )
            return _wait_for_media(cast, media_url, timeout=wait_timeout)
        except Exception as exc:
            last_error = exc
            if attempt == 2:
                raise
            status = cast.media_controller.status
            LOGGER.warning(
                "Cast load did not become active; retrying once "
                "(state=%s, idle_reason=%r, session=%r, content=%r): %s",
                status.player_state,
                status.idle_reason,
                status.media_session_id,
                status.content_id,
                exc,
            )
            try:
                cast.media_controller.update_status()
            except Exception:
                pass
            time.sleep(0.75)

    assert last_error is not None
    raise last_error


def _cast_url(
    device: CastDevice,
    media_url: str,
    content_type: str,
    *,
    title: str | None,
    autoplay: bool,
    loop: bool,
) -> dict[str, str]:
    pychromecast = _load_pychromecast()
    cast = None
    try:
        cast = _connect_direct(pychromecast, device)
        cast.wait(timeout=8)
        player_state = _load_with_retry(
            cast,
            media_url,
            content_type,
            title=title,
            autoplay=autoplay,
            loop=loop,
        )
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
        if cast is not None:
            try:
                cast.disconnect(timeout=1)
            except Exception:
                pass


def cast_file(
    device_identifier: str,
    path: str | Path,
    content_type: str,
    *,
    title: str | None = None,
    autoplay: bool = True,
    loop: bool = False,
) -> dict[str, str]:
    """Publish a local media file and cast it to the selected device."""
    try:
        device = DISCOVERY.resolve(device_identifier)
    except DiscoveryError as exc:
        raise CastError(str(exc)) from exc

    try:
        media_url = MEDIA_SERVER.publish(
            path,
            content_type,
            ttl_seconds=LOOP_MEDIA_TTL_SECONDS if loop else DEFAULT_MEDIA_TTL_SECONDS,
            target_host=device.host,
        )
    except Exception as exc:
        raise CastError(f"Could not prepare media for {device.name}: {exc}") from exc

    return _cast_url(
        device,
        media_url,
        content_type,
        title=title,
        autoplay=autoplay,
        loop=loop,
    )
