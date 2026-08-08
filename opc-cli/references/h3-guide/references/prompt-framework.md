# H3 Prompt Framework

本文件只用于创意拆解，不是可直接提交给 H3 的 Prompt 模板。最终输出必须先读取 MiniMax 官方 `h3-prompt-writing` skill，并转换为对应模式的固定英文结构；对白、歌词和画面文字保留原语言。

## 目录

- 通用结构
- T2V 模板
- I2V 模板
- R2V 生成模板
- R2V 编辑模板
- 声音与文字
- opc 命令模板

## 通用结构

按以下优先级组织 Prompt。越靠前越接近“合同”，越靠后越接近美术修饰。

1. **输出合同**：时长、画幅、连续镜头或剪辑结构、真实/动画媒介。
2. **全局不变量**：身份、产品、Logo、机位、布局、原声音等必须固定的内容。
3. **参考绑定**：逐个说明 `<Picture N>`、`<Video N>`、`<Audio N>` 的唯一职责。
4. **动作时间轴**：按秒或按镜头描述主体动作、状态变化和转场触发点。
5. **镜头语言**：景别、机位、焦段感、运镜速度、对焦、遮挡和剪辑。
6. **视觉语法**：色彩、光线、材质、颗粒、排版、动画工艺。
7. **声音设计**：对白、口型、环境声、拟音、音乐结构和结尾 hit。
8. **文字/MG**：精确文案、出现次数、可读时长、入退场和禁止乱码。
9. **禁止项**：只写最可能出现且会毁掉结果的问题。

让每个镜头包含“主体 + 动作 + 场景 + 镜头 + 声音”，避免只列名词。

## T2V 创意草稿

```text
integrated_multimodal_description: [Shot 1] [用英文写风格、构图、主体、动作、镜头、现场声音；后续切镜使用精确时间戳]

overall_soundscape: [用英文写环境声、动作拟音和非语言人声，不重复对白与现场音乐]

non_diegetic_music: [用英文写观众才能听见的配乐，或 N/A]
```

适合纯文生的强项：真实生活中的异常事件、短片气氛、风格化动画、具有清晰动作弧线的一镜到底。没有固定资产时，不要为了“更丰富”强行添加参考图。

## I2V / FL2VA / L2VA 创意草稿

```text
[先按官方 base-en.txt 写 I2VA、FL2VA 或 L2VA 的精确图片对齐句]

integrated_multimodal_description: [Shot 1] [从首帧发展、连接首尾帧，或逐渐落到尾帧]

overall_soundscape: [环境声与动作拟音]

non_diegetic_music: [配乐或 N/A]
```

首尾帧转场优先寻找两张图之间的“形态同构”：咖啡泡沫到沙丘、织物褶皱到山谷、玻璃反射到水面。把共同的纹理、方向和遮挡瞬间写清楚，比写“丝滑转场”有效。

## R2V 创意草稿

```text
subject_definitions:
[只定义实际承担角色的 Subject、Picture、Video、Audio 标签]

summary:
[以官方任务类型前缀开头的一段摘要]

retention_analysis:
[每个引用标签一行，使用官方固定 retention marker]

detailed_description:
[英文风格开场；随后按 Shot 和时间顺序写详细画面、动作、镜头与现场声音]

overall_soundscape:
[环境声与动作拟音]

non_diegetic_music:
[配乐或 N/A]
```

一组多参考图不要全部写成“风格参考”。把人物三视图绑定为身份，把 moodboard 绑定为场景，把 storyboard 绑定为镜头顺序。

## R2V 编辑约束

在官方 Ref2VA 六字段结构内，把 `<Video 1>` 定义为源视频，并将 `summary` 的任务类型写为 `[video editing ...]`。摘要正文必须以 `The target video is an edited version of <Video 1>.` 开头，再把允许修改和必须保留的内容分别写进 `retention_analysis` 与 `detailed_description`。不要用 `[reference generation]` 代替真正的视频编辑关系。

编辑主体与原主体外形差异大时，同时写“目标是什么”和“原对象哪些属性不得保留”。

## 声音与文字

### 声音

- 指定对白原文、说话人、语言、情绪、音量距离和动作同步点。
- 指定音乐的结构，不要只写曲风：前奏、节拍进入、层次增加、高潮和结尾 hit。
- 指定环境声和关键拟音，避免模型用无关音乐填满空间。
- 参考视频默认携带音轨时，它会占用音频序号；独立音频的 `<Audio N>` 以 `opc` 当前规则为准。若希望独立音频成为 `<Audio 1>`，考虑对视频使用 `--no-reference-video-audio`。

### 文字/MG

- 所有必须正确的字符串逐字给出，并声明“只出现一次”。
- 规定字号感、字重、字距、材质、位置、进入方式、停留时长和退出方式。
- 片头署名要约束姓名/职位不可重复，禁止同一人承担多个职位。
- 动效要绑定节拍或遮挡：线框画出、遮罩揭示、字距展开、残影或硬切；避免只写“炫酷文字”。
- 重要长文案不要把生成模型当排版引擎，优先生成干净底片后在后期叠字。

## opc 命令模板

执行前读取 `opc` skill 并用 `opc video info` 核对当前参数。

```bash
# 文生视频
opc video --workflow h3-t2v \
  --prompt-file prompt.txt \
  --width 864 --height 480 --duration 5 --steps 20 \
  --output ./output

# 首帧/首尾帧
opc video --workflow h3-i2v \
  --prompt-file prompt.txt \
  --first-frame first.png --last-frame last.png \
  --width 864 --height 480 --duration 5 --steps 20 \
  --output ./output

# 多参考/视频编辑：命令行顺序就是 Picture/Video/Audio 序号
opc video --workflow h3-r2v \
  --prompt-file prompt.txt \
  --reference-image identity.png \
  --reference-image scene.png \
  --reference-video motion.mp4 \
  --reference-audio voice.wav \
  --ref-image-size match \
  --width 864 --height 480 --duration 5 --steps 20 \
  --output ./output
```

首次执行优先 dry-run（若当前 CLI 支持），核对媒体序号、帧数、音轨和输出目录，再提交真实任务。
