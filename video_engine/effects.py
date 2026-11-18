"""片段归一化：任意图片/视频 → 统一分辨率/帧率/时长的小片段。"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg
from .spec import Clip, Project

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _cover_filter(size: tuple[int, int]) -> str:
    w, h = size
    # 等比铺满后居中裁切
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


def _kenburns(size: tuple[int, int], fps: int, dur: float, zoom: float, zoom_in: bool) -> str:
    w, h = size
    frames = max(1, int(round(dur * fps)))
    if zoom_in:
        z = f"min(1+{(zoom-1)/frames:.6f}*on,{zoom})"
    else:
        z = f"max({zoom}-{(zoom-1)/frames:.6f}*on,1)"
    # zoompan 输出尺寸用 s=，先放大再缩回保证清晰
    return (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={w}x{h}:fps={fps}"
    )


def build_clip(project: Project, clip: Clip, out: Path) -> float:
    """把单个画面片段渲染成统一格式的 mp4，返回实际时长。"""
    src = project.resolve(clip.source)
    if not src.exists():
        raise FileNotFoundError(f"素材不存在：{src}")

    is_image = src.suffix.lower() in IMAGE_EXT
    dur = clip.duration
    if is_image and dur is None:
        raise ValueError(f"图片片段必须指定 duration：{src.name}")
    if dur is None:
        dur = max(1.0, ffmpeg.duration(src) - clip.in_point)

    w, h = project.size
    fps = project.fps
    eff = clip.effect.type

    if is_image:
        inputs = ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(src)]
        base = _cover_filter((w, h))
        if eff in ("kenburns_in", "kenburns_out"):
            vf = f"{_kenburns((w, h), fps, dur, clip.effect.zoom, eff == 'kenburns_in')},format=yuv420p"
        else:
            vf = f"{base},fps={fps},format=yuv420p"
    else:
        inputs = ["-ss", f"{clip.in_point:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
        vf = f"{_cover_filter((w, h))},fps={fps},format=yuv420p"

    # 转场用「淡入淡出到黑」实现：稳定、时长精确，不用 xfade 链
    if clip.transition_in.type == "fade":
        fi = min(0.4, dur / 4)
        fo = min(0.4, dur / 4)
        vf = f"{vf},fade=t=in:st=0:d={fi:.2f},fade=t=out:st={dur - fo:.2f}:d={fo:.2f}"

    ffmpeg.run([
        *inputs,
        "-an",
        "-vf", vf,
        "-r", str(fps),
        "-t", f"{dur:.3f}",
        *ffmpeg.video_encode_args(),
        str(out),
    ])
    return dur
