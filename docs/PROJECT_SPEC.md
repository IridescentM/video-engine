# project.json 规范（v0）

## 顶层

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| name | string | 否 | 文件名 | 项目名 |
| size | [w, h] | 是 | — | 必须偶数；竖屏 1080×1920，横屏 1920×1080 |
| fps | int | 否 | 25 | 帧率 |
| bgm_volume | float | 否 | 0.18 | BGM 默认音量（0–1） |
| tracks | array | 是 | — | 轨道列表 |

## 轨道

| type | 说明 | 数量限制 |
|---|---|---|
| image | 图片轨道（也可放视频，混排） | v0 仅一条 |
| video | 同上（语义区分） | v0 仅一条 |
| text | 文字叠加 | 可多条 |
| audio | 人声/音效，按 start 延迟插入 | 可多条 |
| bgm | 背景音乐，循环播放 | 可多条 |

## 片段通用字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| source | string | — | 素材路径，相对 project.json 所在目录 |
| start | float | 0 | 时间轴起点（秒）——文本/音频用 |
| duration | float | 自动 | 片段时长；图片必填 |
| in | float | 0 | 视频截取起点 |
| effect | string 或对象 | none | `kenburns_in` / `kenburns_out` / `none` |
| transition_in | string 或对象 | none | `fade` + duration（仅画面轨，作用于与前一片段之间） |

## 文字片段

| 字段 | 默认 | 说明 |
|---|---|---|
| text | — | 必填 |
| start / duration | — | 必填，duration 必须给 |
| style | big_center | `big_center` / `big_top` / `subtitle` / `accent` |
| anim | fade_in | `fade_in` / `none` |

## 音频片段

| 字段 | 默认 | 说明 |
|---|---|---|
| volume | 1.0 | 0–1 |
| fade_in / fade_out | 0 | 秒 |
| loop | false | BGM 自动循环（audio 轨不循环） |

## 示例

```json
{
  "name": "demo",
  "size": [1080, 1920],
  "fps": 25,
  "bgm_volume": 0.12,
  "tracks": [
    { "type": "bgm", "clips": [{ "source": "../assets/bgm.mp3", "fade_in": 1, "fade_out": 2 }] },
    { "type": "image", "clips": [
      { "source": "../assets/a1.png", "duration": 3.0, "effect": "kenburns_in" },
      { "source": "../assets/a2.png", "duration": 3.5, "transition_in": { "type": "fade", "duration": 0.5 } }
    ]},
    { "type": "text", "clips": [
      { "text": "16 年开发", "start": 0.3, "duration": 2.4, "style": "big_center" }
    ]}
  ]
}
```

## 校验规则（不满足直接报错）

1. 必须有一条 image/video 轨，且 v0 只允许一条
2. 图片片段必须有 duration；文字片段必须有 duration
3. 素材文件不存在 → 报错（不静默跳过）
4. size 必须是偶数
5. 未知轨道类型 / 未知 effect 一律报错
