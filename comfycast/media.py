from __future__ import annotations

from pathlib import Path
import tempfile
import time
import uuid

import numpy as np
from PIL import Image


MEDIA_DIR = Path(tempfile.gettempdir()) / "comfycast"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_old_media(max_age_seconds: float = 24 * 3600) -> None:
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
        raise ValueError(f"Image index {image_index} is outside the batch of {len(images)} image(s).")

    array = images[image_index].detach().cpu().float().numpy()
    array = np.clip(array * 255.0 + 0.5, 0, 255).astype(np.uint8)
    if array.ndim != 3 or array.shape[2] not in (1, 3, 4):
        raise ValueError(f"Unsupported image tensor shape: {array.shape}")

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
