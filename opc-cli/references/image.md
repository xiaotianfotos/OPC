# Image - AI 图片生成

基于 ComfyUI 工作流的 AI 图片生成引擎。支持多模型（ERNIE-Image-Turbo/Full、Qwen-Image、Z-Image），内置 Prompt 知识图谱（PromptKG）辅助 prompt 构建与风格探索。

**详细文档：** [SKILL.md](../SKILL.md) 包含环境安装和通用配置。

## 目录

- [配置 ComfyUI 连接](#配置-comfyui-连接)
- [可用工作流](#可用工作流)
- [图片生成](#图片生成)
- [图片编辑](#图片编辑)
- [JSON Prompt 格式](#json-prompt-格式)
- [图片分析](#图片分析)
- [Prompt 知识图谱（KG）](#prompt-知识图谱kg)
- [AI Agent 完整 SOP](#ai-agent-完整-sop)
- [模板系统](#模板系统)
- [评估系统](#评估系统)

## 配置 ComfyUI 连接

```bash
opc config --set-comfyui-host 192.168.100.10
opc config --set-comfyui-port 8188
opc config --set-image-output-dir /vol2/1000/output
```

## 可用工作流

```bash
opc image list
opc image info <alias>
```

常用别名：`ernie-turbo`（8步快速生成）、`ernie-full`（50步高质量，中文文字渲染强）、`qwen-image`、`z-image`、`klein`（Flux2-Klein-9B）、`ideogram4`（Ideogram 4）、`klein-edit`（Klein 图片编辑）。

**ERNIE-Image 可用参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | string | (必需) | 图片描述文本 |
| `width` | int | 1024 | 图片宽度 |
| `height` | int | 1024 | 图片高度 |
| `seed` | int | -1 | 随机种子（-1=随机） |
| `steps` | int | 8(turbo)/50(full) | 采样步数 |
| `cfg` | float | 1(turbo)/4(full) | CFG 引导强度 |

## 图片生成

```bash
# 基础生成
opc image -w ernie-turbo -p "a cat sitting on a windowsill"

# 自定义分辨率和种子
opc image -w ernie-turbo -p "a cat" -P width=1376 -P height=768 -P seed=42

# Ideogram 4，支持 Quality / Default / Turbo preset
opc image -w ideogram4 --text -p "bold cinematic poster, clean typography" -P quality=Turbo

# 使用 JSON 结构化 prompt（推荐）
opc image -w ernie-full -p '{"subject":"美食摄影","style":"photography","mood":"warm","text_content":{"type":"title","content":"秋日味道","position":"top_center"}}'

# 测试连通性
opc image test ernie-turbo -p "test image"
```

**参数：**
- `-w, --workflow` — 工作流别名
- `-p, --prompt` — 提示词（纯文本或 JSON）
- `-P, --param` — 工作流参数 `key=value`，可多次使用

## 图片编辑

基于 ComfyUI 工作流的图片编辑，支持单图/多图输入，默认使用 `klein-edit` 工作流。

```bash
# 基础编辑
opc image-edit --image photo.png -p "add a red hat to the person"

# 指定工作流
opc image-edit -w klein-edit --image photo.png -p "make it look like a painting"

# 多图输入（融合、对比等）
opc image-edit --image ref1.png --image ref2.png -p "blend these two images"

# JSON 结构化 prompt
opc image-edit --image input.jpg -p '{"subject":"add snow","style":"winter"}'

# 覆盖参数
opc image-edit --image photo.png -p "add sunset" --param steps=30 --param seed=42
```

**参数：**
- `-w, --workflow` — 工作流别名（默认 `klein-edit`）
- `--image, -i` — 输入图片路径（可多次指定）
- `-p, --prompt` — 编辑指令（必需）
- `-P, --param` — 工作流参数 `key=value`
- `--text` — 将 prompt 当作纯文本（而非 JSON）

**klein-edit 可用参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | string | (必需) | 编辑指令 |
| `negative_prompt` | string | | 负面提示词 |
| `steps` | int | 20 | 采样步数 |
| `cfg` | float | 5 | CFG 引导强度 |
| `seed` | int | -1 | 随机种子 |

## JSON Prompt 格式（默认格式）

`opc image -p` **默认期望 JSON 格式**。纯文本需加 `--text` 标志。

JSON prompt 自动转换为模型友好的自然语言，相比纯文本有更好的生成质量。字段与 KG 实体分类对齐，可由 AI 根据 skeleton 输出自动组装。

### 字段一览

所有字段可选，按需组合。简单值用字符串，精细控制用对象。

| 字段 | 类型 | 用途 |
|------|------|------|
| `subject` | string 或 object | 主体内容 |
| `style` | string 或 object | 艺术风格 |
| `mood` | string 或 object | 情绪氛围 |
| `composition` | object | 构图方式 |
| `lighting` | object | 光照设定 |
| `background` | object | 背景环境 |
| `color_palette` | object | 色彩方案 |
| `text_content` | object | 图片内文字 |
| `typography_layout` | object | 中文排版 DSL（高级） |
| `confrontation` | object | 对比/对峙构图（高级） |
| `technical_specs` | object | 画质/渲染参数 |
| `layout` | string 或 object | **文字排版布局（推荐）** |
| `negative_constraints` | list | 排除项 |

### 简单用法（字符串值）

直接用字符串描述各维度，适合快速生成：

```json
{
  "subject": "a cat sitting on a windowsill",
  "style": "watercolor painting",
  "mood": "peaceful",
  "lighting": {"type": "natural", "quality": "soft"},
  "color_palette": {"mood": "warm pastel"}
}
```

### 对象用法（精细控制）

每个字段支持展开为对象，提供更精确的控制：

```json
{
  "subject": {
    "main": "a young woman reading a book",
    "details": "sitting cross-legged, glasses, focused expression",
    "position": "center of frame"
  },
  "style": {
    "medium": "digital illustration",
    "techniques": ["watercolor wash", "ink outlines"],
    "references": "Studio Ghibli background art"
  },
  "composition": {
    "framing": "medium shot",
    "angle": "slightly low angle",
    "focus": "the woman and her book"
  },
  "lighting": {
    "type": "natural window light",
    "direction": "side",
    "quality": "soft diffused",
    "color_temperature": "warm afternoon"
  },
  "background": {
    "setting": "indoor cozy room",
    "details": "bookshelves, plants, warm wooden furniture",
    "depth": "layered with bokeh"
  },
  "color_palette": {
    "dominant": ["warm beige", "soft amber"],
    "accent": ["sage green"],
    "mood": "warm and serene"
  },
  "mood": "peaceful, contemplative, nostalgic",
  "negative_constraints": ["blurry", "watermark", "低质量", "变形"]
}
```

### text_content — 图片内文字

指定图片中必须出现的文字内容：

```json
{
  "subject": "a cozy café scene",
  "text_content": {
    "visible_text": ["咖啡时光", "Café Dreams"],
    "typography": "handwritten style, chalkboard text",
    "language": "Chinese and English"
  }
}
```

### typography_layout — 中文排版 DSL

专为中文文字渲染设计的排版控制，支持位置、颜色、渐变、装饰：

```json
{
  "typography_layout": {
    "style": "手写体，清晰可读",
    "lines": [
      {
        "position": "top",
        "segments": [
          {"text": "秋日味道", "color": "深棕", "style": "大号标题"}
        ]
      },
      {
        "position": "bottom_center",
        "segments": [
          {"text": "温暖每一刻", "color": {"from": "橘红", "to": "金黄", "direction": "从左到右"}}
        ],
        "emphasis": "带光晕效果"
      }
    ],
    "decorations": ["星星点缀", "落叶飘散"]
  }
}
```

**position 可选值：** `top`, `second`, `third`, `middle`, `center`, `bottom`, `bottom_center`, `bottom_left`, `bottom_right`, `top_left`, `top_right`, `left`, `right`

### confrontation — 对比构图

用于左右或上下对比的场景：

```json
{
  "confrontation": {
    "layout": "left_vs_right",
    "left": {"name": "健康饮食", "color": "绿色", "feel": "清新活力"},
    "right": {"name": "垃圾食品", "color": "红色", "feel": "油腻沉重"}
  }
}
```

`layout` 可选：`left_vs_right`、`top_vs_bottom`。

### layout — 文字排版布局（推荐）

**所有包含文字的图片都应包含 `layout` 字段。** 验证器会在 `text_content` 或 `typography_layout` 存在但缺少 `layout` 时发出 WARNING。

`layout` 是一个自由格式字段，没有固定 schema，可以是：

1. **简单字符串** — 一句话描述文字位置
2. **结构化对象** — elements + typography + connectors
3. **任意自由格式** — 只要有就行

#### 简单字符串

```json
{
  "layout": "顶部大标题'破茧成蝶'，底部五个阶段从左到右排列：卵→幼虫→蛹→成虫→飞翔"
}
```

#### 结构化对象

```json
{
  "layout": {
    "elements": [
      {"role": "title", "text": "云梦泽", "position": "top-center"},
      {"role": "subtitle", "text": "古代大泽", "position": "below title"},
      {"role": "label", "text": "湖北江汉平原", "position": "left sidebar"}
    ],
    "typography": {"font_style": "serif", "color": "dark brown"},
    "connectors": ["ornate borders between sections"]
  }
}
```

#### 设计原则

1. **列出每个文字元素**及其确切内容和位置
2. **分离"写什么字"和"怎么排版"**
3. **文字内容用字面值** — 模型必须逐字复刻
4. **位置要具体** — top-center, left sidebar, bottom banner 等
5. **全局排版规则集中声明** — 字体、颜色、对齐

### 从 KG skeleton 到 JSON prompt

典型工作流：skeleton 输出的实体 → 直接填入 JSON prompt 字段：

```
KG: style:hand_drawn → "style": {"medium": "hand_drawn illustration"}
KG: mood:warm        → "mood": "warm"
KG: genre:infographic → (融入 subject 描述)
KG: composition:vertical → "composition": {"framing": "vertical 9:16"}
```

## 图片分析

使用视觉模型分析图片内容：

```bash
# 描述图片
opc image analyze photo.png --describe

# 自定义提问
opc image analyze photo.png --describe --prompt "这张图的文字渲染质量如何？"

# 两图对比（迭代优化用）
opc image analyze photo.png --describe --compare reference.png
```

## Prompt 知识图谱（KG）

内置 Prompt 知识图谱，涵盖实体分类（style, subject, mood, composition, lighting, genre, perspective, color_palette, typography, text_content）+ 共现关系 + 模板。

```bash
# 列出所有实体
opc image kg list
opc image kg list --category style

# 实体详情（含关联关系 + 相关模板）
opc image kg info style:photography

# 模糊搜索
opc image kg search food

# 查询与某实体最搭配的元素
opc image kg query subject:food --category lighting --top 5

# 生成 prompt 构建计划（核心）
opc image kg skeleton subject:food style:photography

# 验证实体组合合理性
opc image kg validate style:photography subject:food lighting:soft

# 查找相似 prompt
opc image kg similar subject:food style:photography

# 模板列表 / 按实体查找
opc image kg templates
opc image kg templates --entity mood:nostalgic
```

| 子命令 | 说明 |
|--------|------|
| `list [-c CAT]` | 列出实体，可按分类过滤 |
| `info <entity>` | 详情 + 关联 + 相关模板 |
| `search <keyword>` | 模糊搜索 |
| `query <entity> [-c C] [-n N]` | 搭配推荐 |
| `skeleton <e1> <e2> ...` | Prompt 构建计划 |
| `validate <e1> <e2> ...` | 组合合理性检查 |
| `similar <entities> [-n N]` | 相似 prompt |
| `templates [-e ENTITY]` | 模板列表 / 按实体查找 |

## AI Agent 完整 SOP

KG 驱动的图片生成是一个闭环流程，分为 5 个阶段：

```
阶段 1: 意图识别 → KG 查询
阶段 2: KG 返回上下文 → AI 组装 prompt
阶段 3: AI 调用生图 → 获得结果
阶段 4: AI 分析图片 → 优化 prompt → 重新生图（迭代）
阶段 5: 用户满意 → 经验沉淀回 KG
```

### 阶段 1: 意图识别 → KG 查询

从用户需求中提取关键概念，映射到 KG 实体：

```bash
# 模糊搜索匹配实体
opc image kg search <关键词>

# 如果涉及模板/场景，查看可用模板
opc image kg templates
opc image kg templates --entity <entity>
```

### 阶段 2: KG 返回上下文 → 组装 Prompt

`skeleton` 是核心命令，返回完整构建计划：

```bash
opc image kg skeleton <entity1> <entity2> ...
```

输出包含：
- **filled**: 已确定的维度
- **recommendations**: 每个空缺维度的 Top 3 推荐
- **example_prompts**: 历史参考 prompt
- **template_recommendations**: 关联模板（含场景、分辨率、描述）

AI 读取 skeleton 输出，选择各维度实体，组装 JSON prompt 或自然语言 prompt。

**如果使用模板：**
1. 从 `template_recommendations` 选择模板
2. 读取 `templates/<name>/template.json` 获取 `style_prefix` 和场景 `template`
3. 填充场景参数占位符（`{param}`）
4. 拼接: `style_prefix + scene.template` → 最终 prompt

### 阶段 3: 生图

```bash
opc image -w <model> -p "<assembled prompt>"
# 或
opc image -w <model> -p '<json prompt>'
```

### 阶段 4: 分析 → 优化（迭代）

```bash
# 分析生成结果
opc image analyze output.png --describe

# 与参考图对比
opc image analyze output.png --describe --compare reference.png

# 验证实体组合是否合理
opc image kg validate <chosen entities>

# 根据分析结果调整 prompt，重新生成
```

典型迭代：分析文字清晰度 → 调整布局描述 → 重试 → 对比改善程度。

### 阶段 5: 经验沉淀

用户满意的结果应沉淀回 KG：

- **新实体**: 修改 `~/.opc_cli/opc/kg/extensions.json` 添加实体 + 共现关系
- **新模板**: 创建 `~/.opc_cli/opc/templates/<name>/template.json`
- **新 prompt**: 添加到 `~/.opc_cli/opc/kg/prompt_graph.json` 的 `prompt_index`

仓库中的 `scripts/image/kg/extensions.json`、`scripts/image/templates/` 和
`scripts/image/examples/prompt_graph.json` 是随包提供的内置数据；同名用户数据优先。

## 模板系统

首选模板目录为 `~/.opc_cli/opc/templates/`，内置模板位于
`scripts/image/templates/`，每个模板一个子目录。

**目录结构：**
```
templates/
  sticker_ppt/template.json     # 手账贴纸 PPT
  retro_poster/template.json    # 复古宣传海报
  vintage_ledger/template.json  # 复古手绘绘本 PPT
```

**template.json 格式：**
```json
{
  "name": "vintage_ledger",
  "description": "模板描述...",
  "version": "1.0",
  "source": "PromptKG 推荐: style:hand_drawn + mood:nostalgic",
  "resolution": { "width": 1344, "height": 768 },
  "style_prefix": "风格前缀描述，会拼接到 prompt 前面，",
  "scenes": {
    "title": {
      "desc": "标题/封面页",
      "template": "布局描述，{param} 为占位符...",
      "params": ["main_title", "subtitle"]
    }
  }
}
```

**使用模板生成图片：** AI 读取 `style_prefix` + 选中场景的 `template`，填充参数后拼接为完整 prompt。

**新增模板：**
1. 创建 `~/.opc_cli/opc/templates/<name>/template.json`
2. 在 `~/.opc_cli/opc/kg/extensions.json` 添加实体和共现关系
3. Dashboard 和 CLI 自动发现（无需额外代码）

## 评估系统

多模型对比评估框架，支持增量执行和实时进度。

**数据目录：** `~/.opc_cli/opc/eval/`
- `prompts/` — 测试集（82 个 JSON prompt 文件）
- `results/<alias>/` — 每个模型的生成结果和 `results.json`

### 命令行

```bash
# 查看状态
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py --list

# 跑缺失的测试（所有模型）
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py

# 只跑某个模型
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py --model klein

# 重跑特定 prompt（子串匹配）
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py --rerun xian_food

# 重跑所有失败的
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py --rerun

# 全部重跑
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py --rerun-all

# 覆盖分辨率
uv run --project ~/.claude/skills/opc-cli python scripts/image/eval_runner.py --model klein --resolution 1024x1344
```

**参数：** `--model/-m` 指定模型、`--list/-l` 状态汇总、`--rerun/-r [PROMPT]` 重跑、`--rerun-all` 全部重跑、`--resolution/-R WxH` 覆盖分辨率

### Dashboard 对比

访问 `/evaluate` 可视化对比各模型结果，支持选择最多 3 个工作流。
