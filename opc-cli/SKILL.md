---
name: opc
description: "多引擎 AI 创作工具链。TTS 语音合成（edge-tts / Qwen3-TTS）、ASR 语音识别与卡拉OK字幕、音频压缩分析、ComfyUI 图片生成与编辑、LTX 图生视频、视频转录/理解和字幕级剪辑。使用场景：(1) 文本转语音播放，(2) 音频转录生成 SRT/ASS 字幕，(3) 音频压缩与响度分析，(4) AI 图片生成、编辑与风格探索，(5) Prompt 知识图谱查询与模板发现，(6) 图生视频与首尾帧视频，(7) 视频转录、理解和剪辑。触发词：语音、TTS、ASR、字幕、音频压缩、图片生成、图片编辑、生视频、图生视频、视频理解、prompt、知识图谱、KG、视频剪辑、cut"
---

# opc - AI 创作工具链

TTS + ASR + 音频处理 + AI 图片生成/编辑 + AI 视频生成/理解 + 视频剪辑。

## 环境安装

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd ~/.claude/skills/opc-cli && uv sync
```

跨平台：Linux 用 CUDA，macOS 用 MLX，命令一致。

**模型下载源：**
```bash
opc config --set-model-source modelscope   # 默认
opc config --set-model-source huggingface  # 备选
opc config --set-model-cache-dir ~/models
```

## 快速开始

```bash
opc discover --set-default          # 发现播放设备
opc tts "你好" -e edge-tts          # 生成语音
opc say "你好"                       # 生成并播放
opc asr audio.mp3 --format srt      # 生成字幕
opc image -w ernie-turbo -p "a cat"  # AI 生图
opc video-gen i2v --image frame.png -p "slow camera push-in"  # 图生视频
opc image kg skeleton subject:food style:photography  # KG prompt 规划
```

所有命令通过 `uv run --project ~/.claude/skills/opc-cli python -m scripts.opc` 执行。`opc` 是上述命令的简写别名。

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

AI 图片生成 + 图片编辑 + Prompt 知识图谱 + 模板系统。**详见 [references/image.md](references/image.md)**。

工作流从 `~/.opc_cli/opc/workflows/` 和仓库内置目录合并发现，用户目录中的同名 alias 优先。用 `opc image list` 查看本机实际可用的图片和视频工作流。

核心流程：
```bash
opc image list                                        # 列出可用工作流
opc image -w ernie-full -p "..."                      # 文生图
opc image -w ideogram4 --text -p "poster design"       # Ideogram 4 生图
opc image-edit --image photo.png -p "add a red hat"   # 图片编辑
opc image kg skeleton subject:food style:photography   # KG 规划
opc image analyze output.png --describe               # 分析
```

### `opc image list` / `info` / `import` — 工作流管理

```bash
opc image list                    # 列出可用工作流
opc image info ernie-turbo        # 查看工作流参数详情
opc image import workflow.json --name my-workflow  # 导入工作流
```

### `opc image analyze` — 图片/工作流分析

```bash
opc image analyze output.png --describe     # 视觉模型描述图片
opc image analyze output.png --describe --compare ref.png  # 对比两张图片
opc image analyze workflow.json             # 分析工作流 JSON 结构
```

### `opc image test` — 工作流连通性测试

```bash
opc image test ernie-turbo --prompt "test image"  # 测试工作流连通性
```

### `opc image` — 文生图

```bash
opc image -w ernie-turbo -p "a cat sitting on a windowsill"
opc image -w ernie-full -p '{"subject":"美食摄影","style":"photography"}'
opc image -w klein -p "a beautiful landscape"
```

**参数：** `-w` 工作流别名、`-p` 提示词、`-P` 工作流参数 `key=value`、`--text` 纯文本模式

### `opc image-edit` — 图片编辑

基于 Klein-Edit 等工作流的图片编辑，需要提供输入图片和编辑指令。

```bash
opc image-edit --image photo.png -p "add a red hat to the person"
opc image-edit -w klein-edit --image photo.png -p "make it look like a painting"
opc image-edit --image ref1.png --image ref2.png -p "blend these two images"
opc image-edit --image photo.png -p "add sunset" --param steps=30 --param seed=42
```

**参数：** `-w` 工作流别名(默认 `klein-edit`)、`--image/-i` 输入图片(可多次)、`-p` 编辑指令(必需)、`-P` 工作流参数、`--text` 纯文本模式

### `opc image kg` — Prompt 知识图谱

```bash
opc image kg list                              # 列出所有实体分类
opc image kg list --category style             # 按分类筛选
opc image kg info style:photography            # 实体详情
opc image kg search portrait                   # 模糊搜索
opc image kg query style:cyberpunk            # 查询搭配推荐
opc image kg skeleton subject:food lighting:neon  # 生成 prompt 骨架
opc image kg validate subject:cat style:photography lighting:dramatic  # 验证组合
opc image kg similar subject:cat               # 查找相似 prompt
opc image kg templates                         # 列出模板
opc image kg templates --entity style:cyberpunk  # 按实体查模板
```

## Video 命令

视频生成依赖 ComfyUI 工作流。默认 alias 为 `ltx-i2v` 和 `ltx-flf`，需先确认它们出现在 `opc image list` 中。

```bash
# 单图动画化
opc video-gen i2v --image frame.png -p "camera slowly zooms in"

# 首尾帧过渡
opc video-gen flf --first-frame start.png --last-frame end.png -p "smooth cinematic transition"

# 更快的蒸馏模式
opc video-gen i2v --image frame.png -p "slow motion" --turbo

# 下载在线视频并用 Qwen3-ASR 转录（需要 yt-dlp 和 ffmpeg）
opc video-transcribe "https://example.com/video"

# 使用 OpenAI-compatible 视觉接口理解本地视频
opc video-describe video.mp4
```

**生成参数：** `--workflow/-w` 工作流、`--prompt/-p` 运动描述、`--param/-P key=value` 参数覆盖、`--output/-o` 输出目录、`--turbo` 快速模式。

**视频理解配置：** `opc config --set-video-desc-api-url <url>`、`--set-video-desc-model <name>`，API key 可单独设置，也可复用图片视觉模型配置。

## Audio 命令

音频压缩与分析工具。

```bash
opc audio compress input.mp3 --preset voice   # 人声压缩预设
opc audio compress input.mp3 -t -20 -r 4 -a 10 --release 130  # 自定义参数
opc audio analyze input.mp3                   # 分析响度 (LUFS)
opc audio presets                              # 列出可用预设
```

**压缩参数：** `-t, --threshold` 阈值 dB (默认 -20.0)、`-r, --ratio` 压缩比 (默认 4.0)、`-a, --attack` 启动时间 ms (默认 10.0)、`--release` 释放时间 ms (默认 130.0)、`--knee` 拐点宽度 dB (默认 0.0)、`--makeup` 补偿增益 dB (默认 0.0)、`--mix` 干湿比 0-1 (默认 1.0)、`--preset` 预设名称

**预设：** `voice` 人声优化 (-20dB, 4:1, 10ms, 130ms)、`music` 音乐轻压缩 (-18dB, 2.5:1, 15ms, 200ms)、`limiter` 硬限制器 (-6dB, 20:1, 1ms, 50ms)、`punch` 打击乐冲击感 (-12dB, 6:1, 3ms, 80ms)、`gentle` 极轻压缩 (-24dB, 1.8:1, 30ms, 300ms)

## Cut 命令

基于 ASR 字词级时间戳的视频剪辑。**详见 [references/cut.md](references/cut.md)**。

```bash
opc cut --video video.mp4        # 启动剪辑 Web 界面
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
| `image_output_dir` | | 图片输出目录 |
| `vision_api_url` | | 视觉模型 API URL |
| `vision_model` | | 视觉模型名称 |
| `video_desc_api_url` | | 视频理解 API URL；为空时复用 `vision_api_url` |
| `video_desc_model` | | 视频理解模型；为空时复用 `vision_model` |
| `video_desc_max_frames` | `8` | 非原生视频模型的抽帧数量 |
| `dashboard_host` | `0.0.0.0` | Dashboard 监听地址 |
| `dashboard_port` | `12080` | Dashboard 端口 |
| `model_source` | `modelscope` | 模型下载源 |

```bash
opc config --show
opc config --set-engine qwen
opc config --set-comfyui-host 192.168.1.100
```
