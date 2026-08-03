---
name: opc
description: "多引擎 AI 创作工具链。TTS、ASR、ComfyUI 图片生成、MiniMax H3 视频生成与 SeedVR2 超分、视频剪辑。使用场景：(1) 文本转语音，(2) 音频转录与字幕，(3) AI 图片生成，(4) H3 文生视频/图生视频/参考图视频，(5) 视频超分，(6) 字幕级视频剪辑。触发词：语音、TTS、ASR、字幕、图片生成、视频生成、H3、SeedVR2、prompt、视频剪辑"
---

# opc - AI 创作工具链

TTS + ASR + AI 图片生成 + MiniMax H3 视频生成 + 视频剪辑。

## 环境安装

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd ~/.claude/skills/opc-cli
uv sync
```

跨平台：Linux 用 CUDA，macOS 用 MLX，命令一致。

**模型下载源：**
```bash
opc config --set-model-source modelscope   # 默认
opc config --set-model-source huggingface  # 备选
opc config --set-model-cache-dir /vol2/1000/llm/models
```

## 快速开始

```bash
opc discover --set-default          # 发现播放设备
opc tts "你好" -e edge-tts          # 生成语音
opc say "你好"                       # 生成并播放
opc asr audio.mp3 --format srt      # 生成字幕
opc image -w ernie-turbo -p "a cat"  # AI 生图
opc video -w h3-t2v -p "a rainy neon street"  # H3 视频
opc image kg skeleton subject:food style:photography  # KG prompt 规划
```

所有命令通过 `uv run python scripts/opc.py` 执行。

## TTS 命令

### `opc tts <text>` — 生成语音文件

```bash
opc tts "你好" -e edge-tts                           # edge-tts
opc tts "你好" -e edge-tts --rate +20% --pitch +5Hz  # 带语速/音调
opc tts "你好" -e qwen --speaker Vivian              # qwen 内置音色
opc tts "你好" -e qwen --instruct "用愤怒的语气说"    # 情绪指令
opc tts "你好" -e qwen --mode voice_design --instruct "温柔的女声"  # 声音设计
opc tts "你好" -e qwen --mode voice_clone --ref-audio ref.wav --ref-text "参考"  # 克隆
```

**参数：** `-e` 引擎(edge-tts|qwen)、`-v` 音色、`-l` 语言、`-o` 输出路径、`--stdin` 从 stdin 读
**edge-tts：** `--rate`、`--pitch`、`--volume`
**qwen：** `-m` 模式(custom_voice|voice_design|voice_clone)、`-s` 音色、`-i` 情绪指令、`--ref-audio`、`--ref-text`

### `opc say <text>` — 生成并播放

参数同 `tts`，额外 `-d` 指定播放设备。

### `opc voices` / `opc discover`

```bash
opc voices -e edge-tts   # 322 个音色
opc voices -e qwen       # 9 个内置音色
opc discover --set-default
```

## ASR Pipeline

4 阶段 Pipeline：ASR + Forced Alignment → Sentence Breaking → CSV Fix → Render

```bash
opc asr audio.mp3                    # 转录到 stdout
opc asr audio.mp3 --format srt       # 生成 SRT + ASS
opc asr audio.mp3 --format json -o result.json
opc asr audio.mp3 --format srt --fix-dir ./fixes             # CSV 修正
opc asr audio.mp3 --format srt --resume-from break           # 从断句阶段恢复
```

**参数：** `--format`(text|json|srt|ass)、`--language`、`--model-size`(1.7B|0.6B)、`--style`、`--fix-dir`、`--resume-from`(asr|break|fix|render)

### 断句规则

两遍扫描：Pass 1 按句号分段，Pass 2 按逗号断行。**没有标点绝对不断行。** 超长行由 Check 标记，用 `opc asr-split` 手动拆分：

```bash
opc asr-split audio.lines.json --line 10 --after "理解，"
opc asr audio.mp3 --format srt --resume-from render
```

### CSV 修正格式

在 `--fix-dir` 放 `fix_1.csv`, `fix_2.csv`...，格式：`原文本，新文本`（新文本留空=删除行）。`#` 开头为注释。

## Image 命令

AI 图片生成 + Prompt 知识图谱 + 模板系统。**详见 [references/image.md](references/image.md)**。

核心流程：
```bash
opc image kg skeleton subject:food style:photography  # KG 规划
opc image -w ernie-full -p "..."                       # 生成
opc image analyze output.png --describe                # 分析
```

## Cut 命令

基于 ASR 字词级时间戳的视频剪辑。**详见 [references/cut.md](references/cut.md)**。

```bash
opc cut --video video.mp4        # 启动剪辑 Web 界面
```

## Video 命令

MiniMax H3 本地文生视频、首尾帧图生视频、参考图视频，以及 SeedVR2 超分。详见 [references/video.md](references/video.md)。

```bash
opc video list
opc video -w h3-t2v -p "..." --width 864 --height 480 --duration 5
opc video -w h3-i2v -p "..." --first-frame first.png --last-frame last.png
opc video -w h3-r2v -p "..." --reference-image subject.png
opc video -w h3-t2v-upscale -p "..." --upscale-factor 2
```

## Dashboard

技能管理面板。**详见 [references/dashboard.md](references/dashboard.md)**。

## 配置

配置文件：`~/.opc_cli/opc/config.json`

| 键 | 默认值 | 说明 |
|---|---|---|
| `tts_engine` | `edge-tts` | 默认 TTS 引擎 |
| `edge_voice` | `zh-CN-XiaoxiaoNeural` | edge-tts 音色 |
| `qwen_speaker` | `Vivian` | qwen 音色 |
| `default_device` | | 播放设备 |
| `asr_model_size` | `1.7B` | ASR 模型 |
| `workspace_dir` | `~/opc-workspace` | 工作目录 |
| `comfyui_host` | `127.0.0.1` | ComfyUI 地址 |
| `comfyui_port` | `8188` | ComfyUI 端口 |
| `video_output_dir` | 空 | 视频下载目录，空时复用 output_dir |
| `dashboard_host` | `0.0.0.0` | Dashboard 监听地址 |
| `dashboard_port` | `12080` | Dashboard 端口 |
| `model_source` | `modelscope` | 模型下载源 |

```bash
opc config --show
opc config --set-engine qwen
opc config --set-comfyui-host 192.168.100.10
```
