"""ffmpeg 定位与调用封装。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _candidates() -> list[Path]:
    env = os.environ.get("VIDEO_ENGINE_FFMPEG_DIR")
    if env:
        return [Path(env)]
    here = Path(__file__).resolve()
    repo = here.parents[1]
    roots = [repo]
    if len(here.parents) > 2:
        roots.append(here.parents[2])
    # 兄弟目录里常见的工具位置（本机：D:/money-project/.tools）
    for r in list(roots):
        for sibling in ("money-project", "openhanako", "OH-WorkSpace"):
            cand = r / sibling
            if cand.is_dir():
                roots.append(cand)
    out: list[Path] = []
    for r in dict.fromkeys(roots):
        out.extend(sorted((r / ".tools").glob("ffmpeg-*/bin")))
    return out


def find() -> tuple[str, str]:
    """返回 (ffmpeg, ffprobe) 可执行文件路径。"""
    for d in _candidates():
        exe = d / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        prb = d / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if exe.exists() and prb.exists():
            return str(exe), str(prb)
    for name in ("ffmpeg", "ffprobe"):
        if not shutil.which(name):
            sys.exit(
                "[错误] 找不到 ffmpeg。三种解决方式：\n"
                "  1) 把 ffmpeg 解压到 .tools/ffmpeg-*/bin/\n"
                "  2) 设置环境变量 VIDEO_ENGINE_FFMPEG_DIR 指向 bin 目录\n"
                "  3) 把 ffmpeg 加入 PATH"
            )
    return "ffmpeg", "ffprobe"


FFMPEG, FFPROBE = find()


def run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-1200:]
        raise RuntimeError(f"ffmpeg 失败（{proc.returncode}）\n命令：{' '.join(cmd)}\n{tail}")
    return proc


def duration(path: str | Path) -> float:
    p = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(p.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"读取时长失败：{path}\n{p.stderr[:300]}") from e


def has_audio(path: str | Path) -> bool:
    p = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(p.stdout.strip())
