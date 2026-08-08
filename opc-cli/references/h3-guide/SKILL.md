---
name: h3-guide
description: "MiniMax H3 视频创意规划、参考素材编排、Prompt 设计与迭代质检指南。用于文生视频、首尾帧视频、多图/视频/音频联合参考、角色与物体替换、动作和运镜迁移、背景与光影编辑、台词音色修改、TVC、片头、MG、短剧、产品、电商、游戏 UI、动画及风格化影像；当用户提到 H3、MiniMax 视频、H3 Prompt、参考图视频或希望用 opc-cli 生成/编辑 H3 视频时使用。"
---

# H3 Guide

把模糊创意转成可执行的 MiniMax H3 方案，并通过现有 `opc` skill 运行。本 skill 负责创意决策、素材分工、测试矩阵和质检；Prompt 的最终结构由 MiniMax 官方 `h3-prompt-writing` skill 负责。

## 前置规则

1. 创建、改写或扩写 Prompt 时，先完整读取官方 `h3-prompt-writing` skill；Base 模式读取其 `references/base-en.txt`，Ref2VA 读取其 `references/ref-en.txt`。
2. 需要真正生成或编辑视频时，再读取可用的 `opc` skill 及其 `references/video.md`，以当前 CLI 能力为准。
3. 先检查用户提供的图片、视频和音频。视频至少读取时长、尺寸、帧率和音轨，并抽帧观察；图片实际查看后再分配角色。
4. 用户只要求策划或 Prompt 时，不提交生成任务。用户要求生成、测试或继续迭代时，完成安全的生成、质检和交付。
5. 不把风格词当方案。明确故事或功能、时间节拍、参考素材职责、镜头、声音、不变量和禁止项。

## Prompt 格式归属

| OPC 工作流 | 官方模式 | 最终结构 |
|---|---|---|
| `h3-t2v` | T2VA | `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music` |
| `h3-i2v` + 首帧 | I2VA | 官方首帧对齐句 + Base 三字段 |
| `h3-i2v` + 首尾帧 | FL2VA | 官方首尾帧对齐句 + Base 三字段 |
| `h3-i2v` + 尾帧 | L2VA | 官方尾帧对齐句 + Base 三字段 |
| `h3-r2v` | Ref2VA | `subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music` |

最终 Prompt 使用英文；对白、歌词和画面内文字保留原语言。官方字段、顺序、`[Shot N]`、时间戳、`<Subject N>`、`<Picture N>`、`<Video N>`、`<Audio N>`、`(S1)` 和 `<d>` 语法不得由本指南另行发明或改写。

## 工作流选择

| 目标 | 工作流 | 选择条件 |
|---|---|---|
| 从零生成完整场景 | `h3-t2v` | 不要求固定角色、产品或构图 |
| 固定首帧，或规定首尾状态 | `h3-i2v` | 构图/主体外观由首帧决定，或必须到达尾帧 |
| 多图联合、动作/镜头参考、视频编辑、声音参考 | `h3-r2v` | 任意图片、视频、音频需要作为独立条件 |

默认采用两阶段生成。抽卡、试 Prompt、筛选 seed 时先做低分辨率 5 秒 Turbo 8 steps 预览；确定方案后保持 Prompt、参考素材顺序和 seed 不变，移除 `--turbo`，用 Base 20 steps 按用户目标分辨率最终出片。Turbo 是预览工具，不作为最终交付。H3 在 24 fps 的帧网格上会把 5 秒请求输出为约 5.167 秒；用户指定其他规格时遵从用户并用 `opc video info` 核实现时支持。

## 标准流程

### 1. 把需求拆成约束

提取并确认：

- 发布目标、观众、画幅、时长、分辨率。
- 主体、场景、动作、叙事或功能演示。
- 必须保持的身份、产品、构图、机位、声音和文字。
- 可以变化的部分，以及明确禁止变化的部分。
- 成功标准：观众看完应该感到什么、记住什么、相信什么。

### 2. 给参考素材分配单一职责

先写素材映射表，再写 Prompt。每份素材尽量只有一个主职责：

- 身份图：脸、发型、体型、服装或角色设定。
- 产品图：几何、材质、Logo、结构和颜色。
- 场景图：空间、色彩、光线和美术方向。
- 风格图：排版、材质、画面语言；不要让其覆盖身份。
- 分镜图：镜头顺序和构图变化。
- 视频：动作、表演节奏、运镜、剪辑或原场景。
- 音频：音色、台词、音乐结构或环境声。

`h3-r2v` 的媒体序号由命令行出现顺序决定，Prompt 必须使用完全一致的 `<Picture 1>`、`<Video 1>`、`<Audio 1>`。上限和音轨编号规则以 `opc` 当前文档为准。

### 3. 按官方骨架写 Prompt

先把输出合同、全局不变量、参考绑定、分秒动作、镜头、视觉、声音、文字和禁止项整理为创意约束，再按官方 `h3-prompt-writing` 对应模式写入固定字段。完整的创意拆解方法见 [prompt-framework.md](references/prompt-framework.md)，但其中任何本地模板都不能覆盖官方字段名和顺序。

### 4. 选择风格语法

不要只写“电影感”“高级感”。从 [style-cookbook.md](references/style-cookbook.md) 选择相应的构图、镜头、材质、剪辑、声音和反例。需要可复用视觉参考时，先读 [reference-library.md](references/reference-library.md)，再用 `view_image` 查看具体资产。

涉及审美片、TVC、微距、材质转场、实拍融合或用户要求“惊艳”时，必须再读 [aesthetic-mechanics.md](references/aesthetic-mechanics.md)。提交生成前把审美目标改写成可观察的光学、材料、空间、转场和停留机制；“电影感”“高级感”“丝滑”不能单独作为执行指令。

### 5. 执行编辑策略

角色/物体替换、背景和光影、动作/运镜迁移、多项同时修改、台词/音色编辑，按 [editing-playbook.md](references/editing-playbook.md) 处理。编辑 Prompt 必须先声明原视频不变量，再列出唯一允许变化的部分。

### 6. 测试与迭代

先用 `--turbo` 抽卡并筛选 Prompt/seed，做六格抽帧和关键局部对比，再决定重试。选中方案后必须用相同 Prompt、参考素材顺序和 seed 去掉 `--turbo` 重跑 Base 20 steps，并以 Base 成片完成最终质检。按 [qa-iteration.md](references/qa-iteration.md) 判断是改 Prompt、换参考、拆任务还是承认模型边界；不要仅凭首帧宣布成功。

```bash
# 抽卡：快速验证创意、Prompt 和 seed
opc video -w h3-t2v --prompt-file prompt.txt \
  --width 608 --height 352 --duration 5 --seed 42 --turbo

# 最终出片：复用选中的 Prompt 和 seed，移除 --turbo
opc video -w h3-t2v --prompt-file prompt.txt \
  --width 1376 --height 768 --duration 5 --seed 42 --steps 20
```

`h3-r2v --turbo` 可用于编辑方案预览，但必须重点检查身份、动作、镜头方向和时序保留；最终 Ref2VA 成片同样移除 `--turbo`。

每次运行前先记录一个“美感假设”和一个“最大风险”。技术规格通过不等于创意通过；失败运行保留为研究样本，下一轮只改变最可能的根因。

## 每次规划的交付格式

按下列顺序输出，缺少的项明确写“无”：

1. 创意一句话与成功标准。
2. 工作流、画幅、时长、分辨率、steps，以及当前属于 Turbo 抽卡还是 Base 最终出片。
3. 参考素材映射表及命令行顺序。
4. 可直接保存为文件的完整 Prompt。
5. 可执行的 `opc video` 命令或 dry-run 命令。
6. 首轮测试重点、失败判据和下一轮只改哪个变量。

## 完成标准

- Prompt 与命令中的媒体序号完全一致。
- 参考职责没有互相冲突。
- 声音、文字、镜头和动作都有明确时序或保持规则。
- 生成结果通过实际抽帧、音轨和解码检查。
- 若两次有针对性的迭代收敛到同一缺陷，报告边界并给出拆镜、遮罩合成或后期方案，不继续盲目烧算力。
