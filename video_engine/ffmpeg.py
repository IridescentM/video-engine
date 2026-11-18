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
        bins = sorted((r / ".tools").glob("ffmpeg-*/bin"))
        if not bins:
            continue
        # GPU(NVENC) 需要旧版 SDK：优先 6.x；CPU 优先新版
        import re as _re
        def ver(p: Path) -> tuple:
            m = _re.search(r"ffmpeg-(\d+)\.", str(p))
            return (int(m.group(1)) if m else 0,)
        bins.sort(key=ver, reverse=not os.environ.get("VIDEO_ENGINE_GPU"))
        out.extend(bins)
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

# 资源控制：默认用 2 线程 + 低于正常优先级，避免渲染时把机器拖死
THREADS = int(os.environ.get("VIDEO_ENGINE_THREADS", "2"))
# GPU 编码（NVENC）：显存编码，CPU 只负责解码与滤镜
GPU = os.environ.get("VIDEO_ENGINE_GPU", "0") not in ("0", "false", "False")


def video_encode_args() -> list[str]:
    """返回视频编码参数（CPU 或 GPU）。"""
    if GPU:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "23",
                "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
LOW_PRIORITY = os.environ.get("VIDEO_ENGINE_LOW_PRIORITY", "1") not in ("0", "false", "False")


def run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    if THREADS > 0:
        # 全局滤镜线程限制（-threads 只在输出前生效，放最后会被忽略）
        cmd[1:1] = ["-filter_threads", str(THREADS), "-filter_complex_threads", str(THREADS)]
        if "-threads" not in args and len(cmd) >= 3:
            cmd.insert(len(cmd) - 1, str(THREADS))
            cmd.insert(len(cmd) - 2, "-threads")
    creationflags = 0
    if LOW_PRIORITY and os.name == "nt":
        creationflags = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
    proc = subprocess.run(cmd, capture_output=capture, text=True, encoding="utf-8",
                          errors="replace", creationflags=creationflags)
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
