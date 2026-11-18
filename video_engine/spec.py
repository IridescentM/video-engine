"""时间轴数据模型与校验（project.json 的 schema）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VISUAL_TRACKS = ("image", "video")
AUDIO_TRACKS = ("audio", "bgm")


class SpecError(ValueError):
    """project.json 不合法。"""


@dataclass
class Effect:
    type: str = "none"          # none | kenburns_in | kenburns_out
    zoom: float = 1.08


@dataclass
class Transition:
    type: str = "none"          # none | fade
    duration: float = 0.4


@dataclass
class Clip:
    source: str | None = None
    text: str | None = None
    start: float = 0.0
    duration: float | None = None
    in_point: float = 0.0
    effect: Effect = field(default_factory=Effect)
    transition_in: Transition = field(default_factory=Transition)
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = False
    style: str = "big_center"
    anim: str = "fade_in"        # none | fade_in
    x: str = "center"            # center | top | bottom
    y: str | None = None

    @staticmethod
    def parse(raw: dict[str, Any], where: str) -> "Clip":
        if not isinstance(raw, dict):
            raise SpecError(f"{where}: clip 必须是对象")
        effect = raw.get("effect") or {}
        if isinstance(effect, str):
            effect = {"type": effect}
        transition = raw.get("transition_in") or {}
        if isinstance(transition, str):
            transition = {"type": transition}
        clip = Clip(
            source=raw.get("source"),
            text=raw.get("text"),
            start=float(raw.get("start", 0)),
            duration=None if raw.get("duration") is None else float(raw["duration"]),
            in_point=float(raw.get("in", 0)),
            effect=Effect(type=effect.get("type", "none"), zoom=float(effect.get("zoom", 1.08))),
            transition_in=Transition(
                type=transition.get("type", "none"), duration=float(transition.get("duration", 0.4))
            ),
            volume=float(raw.get("volume", 1.0)),
            fade_in=float(raw.get("fade_in", 0)),
            fade_out=float(raw.get("fade_out", 0)),
            loop=bool(raw.get("loop", False)),
            style=raw.get("style", "big_center"),
            anim=raw.get("anim", "fade_in"),
            x=raw.get("x", "center"),
            y=raw.get("y"),
        )
        return clip


@dataclass
class Track:
    type: str
    clips: list[Clip] = field(default_factory=list)

    @staticmethod
    def parse(raw: dict[str, Any], idx: int) -> "Track":
        t = str(raw.get("type", "")).strip()
        if t not in VISUAL_TRACKS + AUDIO_TRACKS + ("text",):
            raise SpecError(f"track[{idx}]: 未知轨道类型 {t!r}（支持 image/video/text/audio/bgm）")
        clips = [Clip.parse(c, f"track[{idx}].clips[{i}]") for i, c in enumerate(raw.get("clips", []))]
        return Track(type=t, clips=clips)


@dataclass
class Project:
    name: str
    size: tuple[int, int]
    fps: int
    tracks: list[Track]
    base_dir: Path
    bgm_volume: float = 0.18
    subtitle_style: dict[str, Any] = field(default_factory=dict)

    # ---------- 读取 ----------
    @staticmethod
    def load(path: str | Path) -> "Project":
        p = Path(path)
        if not p.exists():
            raise SpecError(f"找不到 project 文件：{p}")
        try:
            raw = json.loads(p.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            raise SpecError(f"JSON 解析失败：{e}") from e

        size = raw.get("size", [1080, 1920])
        if not (isinstance(size, list) and len(size) == 2):
            raise SpecError("size 必须是 [宽, 高]")
        fps = int(raw.get("fps", 25))
        tracks = [Track.parse(t, i) for i, t in enumerate(raw.get("tracks", []))]
        if not tracks:
            raise SpecError("至少要有一条轨道")

        proj = Project(
            name=raw.get("name", p.stem),
            size=(int(size[0]), int(size[1])),
            fps=fps,
            tracks=tracks,
            base_dir=p.parent,
            bgm_volume=float(raw.get("bgm_volume", 0.18)),
            subtitle_style=raw.get("subtitle_style", {}),
        )
        proj.validate()
        return proj

    # ---------- 校验 ----------
    def validate(self) -> None:
        visual = [t for t in self.tracks if t.type in VISUAL_TRACKS]
        if not visual:
            raise SpecError("缺少画面轨道（image 或 video）")
        if len(visual) > 1:
            raise SpecError("v0 只支持一条画面轨道，请把图片和视频放进同一条轨道")
        for t in self.tracks:
            if t.type in VISUAL_TRACKS:
                if not t.clips:
                    raise SpecError("画面轨道没有片段")
                for c in t.clips:
                    if not c.source:
                        raise SpecError("画面片段必须给 source")
            if t.type == "text":
                for c in t.clips:
                    if not c.text:
                        raise SpecError("文字片段必须给 text")
                    if c.duration is None:
                        raise SpecError(f"文字片段需指定 duration：{c.text[:12]}")
            if t.type in AUDIO_TRACKS:
                for c in t.clips:
                    if not c.source:
                        raise SpecError("音频片段必须给 source")
        if self.size[0] % 2 or self.size[1] % 2:
            raise SpecError("size 必须是偶数（H.264 要求）")

    # ---------- 便捷 ----------
    @property
    def visual_clips(self) -> list[Clip]:
        for t in self.tracks:
            if t.type in VISUAL_TRACKS:
                return t.clips
        return []

    def clips_of(self, kind: str) -> list[Clip]:
        out: list[Clip] = []
        for t in self.tracks:
            if t.type == kind:
                out.extend(t.clips)
        return out

    def resolve(self, src: str | None) -> Path:
        if not src:
            raise SpecError("空素材路径")
        p = Path(src)
        return p if p.is_absolute() else (self.base_dir / p).resolve()
