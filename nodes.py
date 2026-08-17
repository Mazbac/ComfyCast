from __future__ import annotations

import asyncio

from typing_extensions import override
from comfy_api.latest import ComfyExtension, Input, Types, io

from .comfycast.cast_service import cast_media
from .comfycast.media import save_image_tensor, save_video_input
from .comfycast.media_server import MEDIA_SERVER


class CastImage(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ComfyCastImage",
            display_name="Cast Image",
            category="ComfyCast",
            description="Cast a ComfyUI image directly to a Google Cast / Chromecast display.",
            inputs=[
                io.Image.Input("image", tooltip="Image batch to cast."),
                io.String.Input(
                    "device",
                    default="",
                    tooltip="Cast device friendly name, UUID, or IP address.",
                ),
                io.Int.Input("image_index", default=0, min=0, max=4096, step=1),
                io.String.Input("title", default="ComfyCast Image"),
            ],
            is_output_node=True,
            outputs=[io.Image.Output("image")],
        )

    @classmethod
    async def execute(
        cls,
        image,
        device: str,
        image_index: int,
        title: str,
    ) -> io.NodeOutput:
        path, content_type = await asyncio.to_thread(
            save_image_tensor,
            image,
            image_index,
        )
        media_url = MEDIA_SERVER.publish(path, content_type)
        await asyncio.to_thread(
            cast_media,
            device,
            media_url,
            content_type,
            title=title,
            autoplay=True,
        )
        return io.NodeOutput(image)


class CastVideo(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ComfyCastVideo",
            display_name="Cast Video",
            category="ComfyCast",
            description="Cast a native ComfyUI video directly to a Google Cast / Chromecast display.",
            inputs=[
                io.Video.Input("video", tooltip="Native ComfyUI VIDEO input."),
                io.String.Input(
                    "device",
                    default="",
                    tooltip="Cast device friendly name, UUID, or IP address.",
                ),
                io.String.Input("title", default="ComfyCast Video"),
                io.Boolean.Input("autoplay", default=True),
            ],
            is_output_node=True,
            outputs=[io.Video.Output("video")],
        )

    @classmethod
    async def execute(
        cls,
        video: Input.Video,
        device: str,
        title: str,
        autoplay: bool,
    ) -> io.NodeOutput:
        path, content_type = await asyncio.to_thread(
            save_video_input,
            video,
            Types.VideoContainer.MP4,
            Types.VideoCodec.H264,
        )
        media_url = MEDIA_SERVER.publish(path, content_type)
        await asyncio.to_thread(
            cast_media,
            device,
            media_url,
            content_type,
            title=title,
            autoplay=autoplay,
        )
        return io.NodeOutput(video)


class ComfyCastExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [CastImage, CastVideo]


async def comfy_entrypoint() -> ComfyCastExtension:
    return ComfyCastExtension()
