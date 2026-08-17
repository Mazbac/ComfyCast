from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import time
import uuid

from PIL import Image


MEDIA_DIR = Path(tempfile.gettempdir()) / "comfycast"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
_CLEANUP_INTERVAL_SECONDS = 10 * 60
_cleanup_lock = threading.Lock()
_last_cleanup = 0.0


def cleanup_old_media(
    max_age_seconds: float = 25 * 3600,
    *,
    force: bool = False,
) -> None:
    global _last_cleanup
    now_monotonic = time.monotonic()
    with _cleanup_lock:
        if not force and now_monotonic - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return
        _last_cleanup = now_monotonic

    cutoff = time.time() - max_age_seconds
    for path in MEDIA_DIR.glob("comfycast-*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def new_media_path(suffix: str) -> Path:
    cleanup_old_media()
    return MEDIA_DIR / f"comfycast-{uuid.uuid4().hex}{suffix}"


def save_image_tensor(images, image_index: int = 0) -> tuple[Path, str]:
    if images is None or len(images) == 0:
        raise ValueError("Image input is empty.")
    if image_index < 0 or image_index >= len(images):
        raise ValueError(
            f"Image index {image_index} is outside the batch of "
            f"{len(images)} image(s)."
        )

    frame = images[image_index].detach()
    if frame.ndim != 3 or frame.shape[2] not in (1, 3, 4):
        raise ValueError(f"Unsupported image tensor shape: {tuple(frame.shape)}")

    # Quantize before crossing GPU -> CPU. This moves 1 byte/channel instead
    # of a float32 tensor and is materially faster for large images.
    array = frame.mul(255).add(0.5).clamp(0, 255).byte().cpu().numpy()

    if array.shape[2] == 1:
        pil_image = Image.fromarray(array[:, :, 0], mode="L")
    elif array.shape[2] == 4:
        pil_image = Image.fromarray(array, mode="RGBA")
    else:
        pil_image = Image.fromarray(array, mode="RGB")

    path = new_media_path(".png")
    pil_image.save(path, format="PNG", optimize=False)
    return path, "image/png"


def save_video_input(video, video_container, video_codec) -> tuple[Path, str]:
    path = new_media_path(".mp4")
    try:
        video.save_to(
            str(path),
            format=video_container,
            codec=video_codec,
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, "video/mp4"
