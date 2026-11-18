"""渲染器：把 project 组装成 mp4。"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from . import effects, ffmpeg, textimg
from .spec import Clip, Project


def _concat_simple(clips: list[Path], out: Path) -> None:
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    ffmpeg.run(["-f", "concat", "-safe", "0", "-i", str(lst),
                *ffmpeg.video_encode_args(), "-an", str(out)])


def _concat_xfade(clips: list[Path], durations: list[float], trans: list[float], fps: int, out: Path) -> None:
    """相邻片段做叠化转场。trans[i] 是第 i 个片段入场转场时长。"""
    args: list[str] = []
    for c in clips:
        args += ["-i", str(c)]

    chains: list[str] = []
    cur = "[0:v]"
    acc = durations[0]
    for i in range(1, len(clips)):
        d = trans[i]
        offset = max(0.0, acc - d)
        tag = f"[x{i}]"
        chains.append(f"{cur}[{i}:v]xfade=transition=fade:duration={d:.3f}:offset={offset:.3f}{tag}")
        cur = tag
        acc = acc + durations[i] - d

    ffmpeg.run([
        *args,
        "-filter_complex", ";".join(chains),
        "-map", cur,
        "-an",
        "-r", str(fps),
        *ffmpeg.video_encode_args(),
        str(out),
    ])


def _mix_audio(project: Project, base: Path, work: Path, out: Path) -> None:
    inputs: list[str] = ["-i", str(base)]
    filters: list[str] = []
    idx = 1
    mix_tags: list[str] = []

    # 人声 / 音效轨
    for clip in project.clips_of("audio"):
        src = project.resolve(clip.source)
        inputs += ["-i", str(src)]
        delay = int(clip.start * 1000)
        parts = [f"adelay={delay}|{delay}", f"volume={clip.volume}"]
        if clip.fade_in:
            parts.append(f"afade=t=in:st={clip.start:.2f}:d={clip.fade_in:.2f}")
        filters.append(f"[{idx}:a]" + ",".join(parts) + f"[a{idx}]")
        mix_tags.append(f"[a{idx}]")
        idx += 1

    # BGM
    for clip in project.clips_of("bgm"):
        src = project.resolve(clip.source)
        inputs += ["-stream_loop", "-1", "-i", str(src)]
        vol = clip.volume if clip.volume != 1.0 else project.bgm_volume
        total = ffmpeg.duration(base)
        parts = [f"volume={vol:.3f}"]
        if clip.fade_in:
            parts.append(f"afade=t=in:st=0:d={clip.fade_in:.2f}")
        fo = clip.fade_out or 1.5
        parts.append(f"afade=t=out:st={max(0, total - fo):.2f}:d={fo:.2f}")
        filters.append(f"[{idx}:a]" + ",".join(parts) + f"[a{idx}]")
        mix_tags.append(f"[a{idx}]")
        idx += 1

    if not mix_tags:
        ffmpeg.run(["-i", str(base), "-c:v", "copy", str(out)])
        return

    if len(mix_tags) == 1:
        filters.append(f"{mix_tags[0]}anull[aout]")
    else:
        filters.append(
            "".join(mix_tags) + f"amix=inputs={len(mix_tags)}:duration=longest:dropout_transition=2,"
            "alimiter=limit=0.95[aout]"
        )

    ffmpeg.run([
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        *ffmpeg.video_encode_args(),
        "-c:a", "aac", "-b:a", "160k",
        "-t", f"{ffmpeg.duration(base):.3f}",
        str(out),
    ])


def _overlay_text(project: Project, base: Path, work: Path, out: Path, duration: float) -> None:
    texts = [(i, c) for i, c in enumerate(project.clips_of("text")) if c.text and c.duration]
    if not texts:
        ffmpeg.run(["-i", str(base), "-c", "copy", str(out)])
        return

    inputs: list[str] = ["-i", str(base)]
    chains: list[str] = []
    cur = "[0:v]"
    for n, (_, clip) in enumerate(texts, start=1):
        png, _anchor = textimg.render(clip.text or "", clip.style, project.size, work / f"text_{n}.png")
        dur = float(clip.duration)
        start = float(clip.start)
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(png)]
        pref = f"[t{n}]"
        if clip.anim == "fade_in":
            chains.append(
                f"[{n}:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1,"
                f"setpts=PTS-STARTPTS+{start:.3f}/TB{pref}"
            )
        else:
            chains.append(f"[{n}:v]format=rgba,setpts=PTS-STARTPTS+{start:.3f}/TB{pref}")
        nxt = f"[v{n}]"
        chains.append(
            f"{cur}{pref}overlay=0:0:enable='between(t,{start:.3f},{start + dur:.3f})'"
            f":format=auto{nxt}"
        )
        cur = nxt

    ffmpeg.run([
        *inputs,
        "-filter_complex", ";".join(chains),
        "-map", cur,
        "-an",
        "-t", f"{duration:.3f}",
        *ffmpeg.video_encode_args(),
        str(out),
    ])


def render(project: Project, out_path: str | Path, keep_tmp: bool = False) -> Path:
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="render_", dir=str(Path.cwd() / ".tmp")))
    work.mkdir(parents=True, exist_ok=True)

    clips = project.visual_clips
    built: list[Path] = []
    durations: list[float] = []
    trans: list[float] = []

    for i, clip in enumerate(clips):
        part = work / f"clip_{i:03d}.mp4"
        d = effects.build_clip(project, clip, part)
        built.append(part)
        durations.append(d)
        trans.append(clip.transition_in.duration if clip.transition_in.type == "fade" else 0.0)
        print(f"  片段 {i + 1}/{len(clips)}  {Path(clip.source).name}  {d:.2f}s")
        gap = float(os.environ.get("VIDEO_ENGINE_SLEEP_AFTER_CLIP", "0"))
        if gap > 0:
            time.sleep(gap)   # 主动让路，降低平均 CPU 占用

    base = work / "base.mp4"
    if len(built) == 1:
        base = built[0]
    else:
        # v0.1：统一走 concat（转场已在片段内用淡入淡出实现），时长精确可预测
        _concat_simple(built, base)

    with_text = work / "with_text.mp4"
    base_dur = ffmpeg.duration(base)
    _overlay_text(project, base, work, with_text, base_dur)

    _mix_audio(project, with_text, work, out)

    print(f"\n完成：{out}")
    print(f"分辨率 {project.size[0]}×{project.size[1]} · {project.fps}fps · 时长 {ffmpeg.duration(out):.2f}s")
    if not keep_tmp:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"中间文件：{work}")
    return out
