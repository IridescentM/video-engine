"""video_engine —— 代码版时间轴视频引擎（v0）

用法：
    python -m video_engine render examples/project.json -o out/demo.mp4

设计：
    project.json（时间轴） → 归一化片段 → 拼接/转场 → 文字叠加 → 混音 → mp4
    所有中间文件落在 .tmp/，最终产物落在你指定的 out 路径。
"""

__version__ = "0.1.0"
