# video-engine

代码版时间轴视频引擎：**写一份 JSON，渲染一条视频**，无需 GUI、无需剪辑软件、可被 agent 直接调用。

```bash
python -m video_engine validate examples/project.json
python -m video_engine render examples/project.json -o out/demo.mp4
```

## 它是什么

把一个视频拆成**时间轴数据**（轨道 + 片段 + 时间点 + 特效），再由 ffmpeg 渲染成 mp4。
agent 改一个数字、重渲染一次，就能批量出片——这是"自动化视频生产"的最小可用形态。

```
project.json
   ├─ image/video 轨  → 归一化（分辨率/帧率/时长/推拉）
   ├─ text 轨         → PIL 渲染透明 PNG → 叠加 + 淡入
   ├─ audio 轨        → 人声/音效，按时间点延迟
   └─ bgm 轨          → 循环 + 音量 + 淡入淡出
                ↓
        ffmpeg 合成 → mp4（H.264 / AAC）
```

## 依赖

- Python 3.10+
- ffmpeg（三种方式任选）
  1. 解压到 `../money-project/.tools/ffmpeg-*/bin/`（本机已就绪）
  2. 设置 `VIDEO_ENGINE_FFMPEG_DIR` 指向 bin 目录
  3. 加入 PATH
- `pip install -r requirements.txt`

## 能力（v0）

| 能做 | 不支持（计划中） |
|---|---|
| 图片/视频片段拼接 | 画中画（多画面轨） |
| 叠化转场（fade） | 其它转场（推/擦/缩放） |
| Ken Burns 推拉（放大/缩小） | 关键帧自定义曲线 |
| 文字叠加 + 淡入 + 描边 | 花字/贴纸/动画字体 |
| 人声/音效按时间点插入 | 语音自动对齐（TTS 内建） |
| BGM 循环 + 音量 + 淡入淡出 | 音频闪避（ducking） |

## 典型用法

1. **文案转视频**：先用 `text2video`（在 money-project 里）生成配音，再在这里排素材
2. **批量模板**：一份 project.json 改 `text` 和 `source` 就是新片
3. **agent 调用**：`python -m video_engine render xxx.json -o xxx.mp4`，成功返回 0

## 目录

```
video_engine/    引擎代码（spec / effects / textimg / render / cli）
examples/        示例 project.json
assets/          示例素材
out/             渲染产物（gitignore）
docs/            规范与设计
```

## 设计原则

- **时间轴是唯一真源**：任何效果都必须能写进 JSON，不靠手工点
- **渲染可重复**：同样的 JSON 永远出同样的片（素材不变）
- **失败要吵**：素材缺失、时长冲突、参数非法都直接报错，不静默降级

## 资源控制（渲染时不卡）

| 环境变量 | 默认 | 作用 |
|---|---|---|
| `VIDEO_ENGINE_THREADS` | 2 | 编码/滤镜线程数；越小越不卡 |
| `VIDEO_ENGINE_LOW_PRIORITY` | 1 | 进程设为「低于正常」优先级 |
| `VIDEO_ENGINE_GPU` | 0 | 1 = 用 NVENC 显卡编码（需要 ffmpeg 6.x） |
| `VIDEO_ENGINE_SLEEP_AFTER_CLIP` | 0 | 每渲染完一个片段主动 sleep N 秒，压低平均占用 |

实测（53.6 秒预览，1080×1920 素材降到 720×1280）：

| 模式 | 耗时 | CPU 占用 |
|---|---|---|
| 默认（CPU 全速） | ~20s | 95%+ |
| 2 线程 + 低优先级 | 29s | 60–70% |
| GPU(NVENC) + 4 线程 | 16s | 40–78% |
| **GPU + 2 线程 + 每段 sleep 1.5s** | ~90s | **41%** |

推荐组合（边工作边渲染）：

```bash
VIDEO_ENGINE_GPU=1 VIDEO_ENGINE_THREADS=2 VIDEO_ENGINE_SLEEP_AFTER_CLIP=1.5 \
python -m video_engine render project.json -o out.mp4
```
