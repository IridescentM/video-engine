"""命令行入口：python -m video_engine render project.json -o out.mp4"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .spec import Project, SpecError
from . import render as renderer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="video_engine", description="代码版时间轴视频引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="渲染 project.json 为 mp4")
    r.add_argument("project", help="project.json 路径")
    r.add_argument("-o", "--out", required=True, help="输出 mp4 路径")
    r.add_argument("--keep-tmp", action="store_true", help="保留中间文件便于排查")

    v = sub.add_parser("validate", help="只校验 project.json")
    v.add_argument("project")

    args = ap.parse_args(argv)

    if args.cmd == "validate":
        try:
            p = Project.load(args.project)
        except SpecError as e:
            print(f"[失败] {e}")
            return 1
        print(f"[通过] 合法：{p.name} · {p.size[0]}×{p.size[1]} · {p.fps}fps · {len(p.tracks)} 条轨道")
        return 0

    try:
        p = Project.load(args.project)
    except SpecError as e:
        print(f"[失败] {e}")
        return 2

    print(f"渲染 {p.name} → {args.out}")
    try:
        renderer.render(p, args.out, keep_tmp=args.keep_tmp)
    except Exception as e:
        print(f"[失败] {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
