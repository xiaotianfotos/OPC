# 05 - 飞牛OS AI环境部署

> 本期视频教程：在 fnOS（飞牛OS）上一键配置 Qwen3-TTS、Qwen3-ASR

---

## Step 1: 配置魔搭 ModelScope

**目的：** 魔搭默认把模型下载到系统目录，飞牛OS系统盘空间有限。我们把模型路径改到存储盘 `/vol2/1000/AI/models`，避免撑爆系统盘。这个目录可以随意填写

### 1. 安装 ModelScope CLI

```bash
uv tool install modelscope
```

### 2. 配置环境变量

```bash
echo 'export MODELSCOPE_CACHE="/vol2/1000/AI/models"' >> ~/.bashrc && source ~/.bashrc
```

### 3. 下载模型

配置生效后，使用以下命令下载模型：

```bash
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

### 4. 验证

```bash
echo $MODELSCOPE_CACHE
```

