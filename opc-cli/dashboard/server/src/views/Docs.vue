<template>
  <div class="docs-page">
    <!-- Mobile Header -->
    <header class="mobile-header">
      <router-link to="/" class="mobile-logo">OPC</router-link>
      <button class="menu-toggle" @click="toggleSidebar">☰</button>
    </header>

    <!-- Sidebar Overlay -->
    <div class="sidebar-overlay" :class="{ active: sidebarOpen }" @click="toggleSidebar"></div>

    <div class="layout">
      <!-- Sidebar -->
      <aside class="sidebar" :class="{ open: sidebarOpen }">
        <div class="sidebar-header">
          <router-link to="/" class="sidebar-logo">OPC</router-link>
          <div class="sidebar-version">CLI Documentation v1.0</div>
        </div>

        <nav>
          <div class="nav-section">
            <div class="nav-title">快速开始</div>
            <ul class="nav-list">
              <li class="nav-item"><a href="#installation" @click.prevent="scrollToSection">安装</a></li>
              <li class="nav-item"><a href="#quickstart" @click.prevent="scrollToSection">快速开始</a></li>
              <li class="nav-item"><a href="#config" @click.prevent="scrollToSection">配置</a></li>
            </ul>
          </div>

          <div class="nav-section">
            <div class="nav-title">TTS 命令</div>
            <ul class="nav-list">
              <li class="nav-item">
                <a href="#tts" @click.prevent="scrollToSection">
                  <span class="command">opc tts</span>
                  <span class="desc">生成语音文件</span>
                </a>
              </li>
              <li class="nav-item">
                <a href="#say" @click.prevent="scrollToSection">
                  <span class="command">opc say</span>
                  <span class="desc">生成并播放</span>
                </a>
              </li>
              <li class="nav-item">
                <a href="#voices" @click.prevent="scrollToSection">
                  <span class="command">opc voices</span>
                  <span class="desc">列出音色</span>
                </a>
              </li>
            </ul>
          </div>

          <div class="nav-section">
            <div class="nav-title">ASR 命令</div>
            <ul class="nav-list">
              <li class="nav-item">
                <a href="#asr" @click.prevent="scrollToSection">
                  <span class="command">opc asr</span>
                  <span class="desc">语音识别</span>
                </a>
              </li>
              <li class="nav-item">
                <a href="#asr-split" @click.prevent="scrollToSection">
                  <span class="command">opc asr-split</span>
                  <span class="desc">拆分字幕</span>
                </a>
              </li>
            </ul>
          </div>

          <div class="nav-section">
            <div class="nav-title">工具命令</div>
            <ul class="nav-list">
              <li class="nav-item">
                <a href="#cut" @click.prevent="scrollToSection">
                  <span class="command">opc cut</span>
                  <span class="desc">视频剪辑</span>
                </a>
              </li>
              <li class="nav-item">
                <a href="#discover" @click.prevent="scrollToSection">
                  <span class="command">opc discover</span>
                  <span class="desc">设备发现</span>
                </a>
              </li>
              <li class="nav-item">
                <a href="#config-cmd" @click.prevent="scrollToSection">
                  <span class="command">opc config</span>
                  <span class="desc">配置管理</span>
                </a>
              </li>
            </ul>
          </div>
        </nav>
      </aside>

      <!-- Main Content -->
      <main class="main">
        <h1>OPC CLI 文档</h1>
        <p>多引擎 TTS + Qwen3-ASR 语音识别 + 字词级视频剪辑的完整命令参考。</p>

        <!-- Installation -->
        <h2 id="installation">安装</h2>

        <h3>环境要求</h3>
        <ul style="color: var(--text-secondary); margin: 1rem 0; padding-left: 1.5rem;">
          <li>Python 3.10+</li>
          <li>uv 包管理器</li>
          <li>NVIDIA GPU (CUDA) 或 Apple Silicon (MLX)</li>
        </ul>

        <h3>安装步骤</h3>
        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">安装 uv</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">curl -LsSf https://astral.sh/uv/install.sh | sh</span>
            </div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-purple);"></div>
            <span class="command-title">克隆并安装依赖</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">cd ~/.claude/skills/opc-cli</span>
            </div>
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">uv sync --extra cuda  <span class="code-comment"># Linux + NVIDIA</span></span>
            </div>
            <div class="command-line">
              <span class="command-prompt">#</span>
              <span class="command-text">uv sync --extra mlx   <span class="code-comment"># macOS + Apple Silicon</span></span>
            </div>
          </div>
        </div>

        <!-- Quick Start -->
        <h2 id="quickstart">快速开始</h2>

        <div class="example-grid">
          <div class="example-card">
            <div class="example-header">1. 发现并设置播放设备</div>
            <div class="example-body">
              <div class="command-line">
                <span class="command-prompt">$</span>
                <span class="command-text"><span class="code-keyword">opc discover</span> <span class="code-flag">--set-default</span></span>
              </div>
            </div>
          </div>

          <div class="example-card">
            <div class="example-header">2. 生成语音</div>
            <div class="example-body">
              <div class="command-line">
                <span class="command-prompt">$</span>
                <span class="command-text"><span class="code-keyword">opc tts</span> <span class="code-string">"你好，世界！"</span></span>
              </div>
            </div>
          </div>

          <div class="example-card">
            <div class="example-header">3. 生成并播放</div>
            <div class="example-body">
              <div class="command-line">
                <span class="command-prompt">$</span>
                <span class="command-text"><span class="code-keyword">opc say</span> <span class="code-string">"任务完成"</span></span>
              </div>
            </div>
          </div>

          <div class="example-card">
            <div class="example-header">4. 语音识别生成字幕</div>
            <div class="example-body">
              <div class="command-line">
                <span class="command-prompt">$</span>
                <span class="command-text"><span class="code-keyword">opc asr</span> <span class="code-arg">audio.mp3</span> <span class="code-flag">--format</span> <span class="code-arg">srt</span></span>
              </div>
            </div>
          </div>
        </div>

        <!-- Configuration -->
        <h2 id="config">配置</h2>

        <p>配置文件位于 <code>~/.opc_cli/opc/config.json</code></p>

        <table>
          <thead>
            <tr>
              <th>配置项</th>
              <th>默认值</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>tts_engine</code></td>
              <td><code>edge-tts</code></td>
              <td>默认 TTS 引擎</td>
            </tr>
            <tr>
              <td><code>edge_voice</code></td>
              <td><code>zh-CN-XiaoxiaoNeural</code></td>
              <td>edge-tts 默认音色</td>
            </tr>
            <tr>
              <td><code>qwen_speaker</code></td>
              <td><code>Vivian</code></td>
              <td>Qwen 默认音色</td>
            </tr>
            <tr>
              <td><code>qwen_model_size</code></td>
              <td><code>1.7B</code></td>
              <td>模型大小 (1.7B/0.6B)</td>
            </tr>
            <tr>
              <td><code>default_device</code></td>
              <td>-</td>
              <td>默认播放设备</td>
            </tr>
            <tr>
              <td><code>asr_model_size</code></td>
              <td><code>1.7B</code></td>
              <td>ASR 模型大小</td>
            </tr>
            <tr>
              <td><code>workspace_dir</code></td>
              <td><code>~/opc-workspace</code></td>
              <td>工作目录</td>
            </tr>
          </tbody>
        </table>

        <!-- TTS Commands -->
        <h2 id="tts">opc tts</h2>
        <p>生成语音文件。支持 edge-tts（微软在线）和 Qwen3-TTS（本地模型）双引擎。</p>

        <h3>用法</h3>
        <pre><code>opc tts <span class="code-arg">&lt;text&gt;</span> [<span class="code-flag">options</span>]</code></pre>

        <h3>参数</h3>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">text</div>
              <div class="param-meta">
                <span class="tag tag-required">必需</span>
              </div>
            </div>
            <div class="param-desc">要合成的文本。也可使用 <code>--stdin</code> 从标准输入读取</div>
          </div>

          <div class="param-item">
            <div>
              <div class="param-name">-e, --engine</div>
              <div class="param-meta">
                <span class="tag tag-optional">可选</span>
                <span class="tag tag-engine">引擎</span>
              </div>
            </div>
            <div>
              <div class="param-desc">TTS 引擎: <code>edge-tts</code> | <code>qwen</code></div>
              <div class="param-default">默认: 从配置读取</div>
            </div>
          </div>

          <div class="param-item">
            <div>
              <div class="param-name">-o, --output</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">输出文件路径</div>
              <div class="param-default">默认: /tmp/opc_tts_output.mp3</div>
            </div>
          </div>

          <div class="param-item">
            <div>
              <div class="param-name">-f, --format</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">输出格式: <code>mp3</code> | <code>wav</code></div>
              <div class="param-default">默认: mp3</div>
            </div>
          </div>
        </div>

        <h4>edge-tts 选项</h4>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">-v, --voice</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">音色名称，如 <code>zh-CN-XiaoxiaoNeural</code></div>
              <div class="param-default">默认: zh-CN-XiaoxiaoNeural</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--rate</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">语速，格式: <code>+N%</code> 或 <code>-N%</code></div>
              <div class="param-default">默认: +0%</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--pitch</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">音调，格式: <code>+NHz</code> 或 <code>-NHz</code></div>
              <div class="param-default">默认: +0Hz</div>
            </div>
          </div>
        </div>

        <h4>Qwen 选项</h4>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">-m, --mode</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">模式: <code>custom_voice</code> | <code>voice_design</code> | <code>voice_clone</code></div>
              <div class="param-default">默认: custom_voice</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-s, --speaker</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">内置音色: Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee</div>
              <div class="param-default">默认: Vivian</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-i, --instruct</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">情绪/风格指令，如 "用愤怒的语气说"</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--ref-audio</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">参考音频路径（voice_clone 模式）</div>
          </div>
        </div>

        <h3>示例</h3>
        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">基础用法</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc tts "你好，世界！"</span>
            </div>
            <div class="command-output">Generated: /tmp/opc_tts_output.mp3</div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-purple);"></div>
            <span class="command-title">edge-tts 带参数</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc tts "你好" -e edge-tts --rate +20% --pitch +5Hz</span>
            </div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-pink);"></div>
            <span class="command-title">Qwen 带情绪指令</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc tts "你好" -e qwen --speaker Vivian --instruct "用愤怒的语气说"</span>
            </div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-yellow);"></div>
            <span class="command-title">声音设计</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc tts "你好" -e qwen --mode voice_design --instruct "温柔的女声，音调偏高"</span>
            </div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-orange);"></div>
            <span class="command-title">声音克隆</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc tts "你好" -e qwen --mode voice_clone --ref-audio ref.wav --ref-text "参考文本"</span>
            </div>
          </div>
        </div>

        <!-- opc say -->
        <h2 id="say">opc say</h2>
        <p>生成语音并立即在默认设备上播放。参数与 <code>opc tts</code> 相同，额外支持 <code>--device</code> 指定播放设备。</p>

        <h3>额外参数</h3>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">-d, --device</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">播放设备名称，覆盖默认配置</div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">示例</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc say "任务已完成" --device "Living Room HomePod"</span>
            </div>
            <div class="command-output">Generated audio: /tmp/opc_say_temp.mp3<br>Streaming to device: Living Room HomePod...<br>Cleaned up: /tmp/opc_say_temp.mp3</div>
          </div>
        </div>

        <!-- opc voices -->
        <h2 id="voices">opc voices</h2>
        <p>列出指定引擎的可用音色。</p>

        <h3>用法</h3>
        <pre><code>opc voices [<span class="code-flag">-e</span> <span class="code-arg">engine</span>]</code></pre>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">示例</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc voices -e edge-tts  <span class="code-comment"># 列出 322 个 edge-tts 音色</span></span>
            </div>
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc voices -e qwen      <span class="code-comment"># 列出 9 个 Qwen 内置音色</span></span>
            </div>
          </div>
        </div>

        <!-- opc asr -->
        <h2 id="asr">opc asr</h2>
        <p>语音识别与字幕生成。基于 Qwen3-ASR 的 4 阶段 Pipeline 架构。</p>

        <h3>Pipeline 流程</h3>
        <div class="pipeline-viz">
          <div class="pipeline-stage">
            <div class="stage-box active">ASR +<br>强制对齐</div>
            <div class="stage-output">→ .raw.json</div>
          </div>
          <span class="stage-arrow">→</span>
          <div class="pipeline-stage">
            <div class="stage-box">智能断句</div>
            <div class="stage-output">→ .lines.json</div>
          </div>
          <span class="stage-arrow">→</span>
          <div class="pipeline-stage">
            <div class="stage-box">CSV 修正</div>
            <div class="stage-output">→ 更新</div>
          </div>
          <span class="stage-arrow">→</span>
          <div class="pipeline-stage">
            <div class="stage-box">渲染输出</div>
            <div class="stage-output">→ .srt + .ass</div>
          </div>
        </div>

        <h3>用法</h3>
        <pre><code>opc asr <span class="code-arg">&lt;audio&gt;</span> [<span class="code-flag">options</span>]</code></pre>

        <h3>参数</h3>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">audio</div>
              <div class="param-meta"><span class="tag tag-required">必需</span></div>
            </div>
            <div class="param-desc">音频文件路径 (wav, mp3, flac 等)</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-f, --format</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">输出格式: <code>text</code> | <code>json</code> | <code>srt</code> | <code>ass</code></div>
              <div class="param-default">默认: text</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-l, --language</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">语言提示: Chinese, English, Japanese 等</div>
              <div class="param-default">默认: 自动检测</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--model-size</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">模型大小: <code>1.7B</code> | <code>0.6B</code></div>
              <div class="param-default">默认: 1.7B</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--fix-dir</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">CSV 修正文件目录（包含 fix_*.csv）</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--resume-from</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">从指定阶段恢复: <code>asr</code> | <code>break</code> | <code>fix</code> | <code>render</code></div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--max-chars</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">每行最大字符数 (最大 20)</div>
              <div class="param-default">默认: 14</div>
            </div>
          </div>
        </div>

        <h3>示例</h3>
        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">简单转录</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc asr audio.mp3</span>
            </div>
            <div class="command-output">这是音频的转录文本内容...</div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-purple);"></div>
            <span class="command-title">生成字幕</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc asr audio.mp3 --format srt</span>
            </div>
            <div class="command-output">Stage 1: ASR + Forced Alignment ✓<br>Stage 2: Sentence Breaking ✓<br>Stage 3: CSV Fix (0 files) ✓<br>Stage 4: Render ✓<br>Saved: audio.srt<br>Saved: audio.ass</div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-pink);"></div>
            <span class="command-title">使用 CSV 修正</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc asr audio.mp3 --format srt --fix-dir ./fixes</span>
            </div>
            <div class="command-output">Loading fixes from ./fixes/fix_1.csv<br>Applied 3 corrections</div>
          </div>
        </div>

        <div class="note">
          <div class="note-title">CSV 修正文件格式</div>
          <p>在 fix_dir 目录下放置 <code>fix_1.csv</code>, <code>fix_2.csv</code>... 文件：</p>
          <pre style="margin-top: 0.75rem;"><code>被替换的文字,目标文字
Cloud Code,Claude Code
哈喽是,hallucination</code></pre>
        </div>

        <!-- opc asr-split -->
        <h2 id="asr-split">opc asr-split</h2>
        <p>拆分超长字幕行。当 Check 阶段检测到超长行时使用。</p>

        <h3>用法</h3>
        <pre><code>opc asr-split <span class="code-arg">&lt;lines.json&gt;</span> [<span class="code-flag">options</span>]</code></pre>

        <h3>参数</h3>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">lines_json</div>
              <div class="param-meta"><span class="tag tag-required">必需</span></div>
            </div>
            <div class="param-desc">lines.json 文件路径</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--line</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">要拆分的行号（从 1 开始）</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--after</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">在该文本之后拆分（必须唯一匹配）</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--csv</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">CSV 文件，包含多行拆分规则</div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">单行拆分</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc asr-split audio.lines.json --line 10 --after "理解，"</span>
            </div>
          </div>
        </div>

        <!-- opc cut -->
        <h2 id="cut">opc cut</h2>
        <p>基于 ASR 字词级时间戳的视频剪辑。启动 Web 服务器提供可视化剪辑界面。</p>

        <h3>用法</h3>
        <pre><code>opc cut [<span class="code-flag">options</span>]</code></pre>

        <h3>参数</h3>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">-v, --video</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">视频文件路径（可选，可通过 Web UI 上传）</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-j, --json</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">已有的 ASR 结果 JSON 文件路径</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-p, --port</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div>
              <div class="param-desc">服务器端口</div>
              <div class="param-default">默认: 8080</div>
            </div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">--no-browser</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">不自动打开浏览器</div>
          </div>
        </div>

        <h3>界面操作</h3>
        <table>
          <thead>
            <tr>
              <th>操作</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>双击字词</strong></td>
              <td>删除/恢复该字</td>
            </tr>
            <tr>
              <td><strong>拖拽选择</strong></td>
              <td>选中多个连续字词</td>
            </tr>
            <tr>
              <td><strong>Delete 键</strong></td>
              <td>删除选中的字词/间隙</td>
            </tr>
            <tr>
              <td><strong>Ctrl+A</strong></td>
              <td>全选</td>
            </tr>
            <tr>
              <td><strong>双击间隙</strong></td>
              <td>删除/恢复无声间隙（≥0.5s）</td>
            </tr>
          </tbody>
        </table>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">启动剪辑服务器</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc cut --video /path/to/video.mp4</span>
            </div>
            <div class="command-output">[OPC] Starting Cut Dashboard server...<br>[OPC] Server started at http://localhost:8080<br>[OPC] Browser opened.</div>
          </div>
        </div>

        <!-- opc discover -->
        <h2 id="discover">opc discover</h2>
        <p>发现局域网内的 AirPlay 和 DLNA 播放设备。</p>

        <h3>用法</h3>
        <pre><code>opc discover [<span class="code-flag">options</span>]</code></pre>

        <h3>参数</h3>
        <div class="param-list">
          <div class="param-item">
            <div>
              <div class="param-name">--set-default</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">如果只有一个设备，自动设为默认</div>
          </div>
          <div class="param-item">
            <div>
              <div class="param-name">-q, --quiet</div>
              <div class="param-meta"><span class="tag tag-optional">可选</span></div>
            </div>
            <div class="param-desc">静默模式，不输出设备列表</div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">示例</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc discover</span>
            </div>
            <div class="command-output">AirPlay Devices:<br>  • Living Room (Apple TV)<br>  • Bedroom (HomePod)<br><br>DLNA Devices:<br>  • Samsung TV</div>
          </div>
        </div>

        <!-- opc config -->
        <h2 id="config-cmd">opc config</h2>
        <p>查看和管理配置。</p>

        <h3>用法</h3>
        <pre><code>opc config [<span class="code-flag">--show</span>] [<span class="code-flag">--set-xxx</span> <span class="code-arg">value</span>]</code></pre>

        <h3>常用配置命令</h3>
        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-cyan);"></div>
            <span class="command-title">查看配置</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc config --show</span>
            </div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-purple);"></div>
            <span class="command-title">设置默认引擎和音色</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc config --set-engine qwen --set-speaker Vivian</span>
            </div>
          </div>
        </div>

        <div class="command-block">
          <div class="command-header">
            <div class="command-dot" style="background: var(--accent-pink);"></div>
            <span class="command-title">设置默认设备</span>
          </div>
          <div class="command-body">
            <div class="command-line">
              <span class="command-prompt">$</span>
              <span class="command-text">opc config --device "Living Room HomePod"</span>
            </div>
          </div>
        </div>

        <h3>所有配置选项</h3>
        <table>
          <thead>
            <tr>
              <th>选项</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr><td><code>--set-engine</code></td><td>设置默认 TTS 引擎</td></tr>
            <tr><td><code>--set-voice</code></td><td>设置 edge-tts 默认音色</td></tr>
            <tr><td><code>--set-mode</code></td><td>设置 Qwen 默认模式</td></tr>
            <tr><td><code>--set-speaker</code></td><td>设置 Qwen 默认音色</td></tr>
            <tr><td><code>--set-model-size</code></td><td>设置模型大小</td></tr>
            <tr><td><code>--device</code></td><td>设置默认播放设备</td></tr>
            <tr><td><code>--set-asr-model-size</code></td><td>设置 ASR 模型大小</td></tr>
            <tr><td><code>--set-asr-language</code></td><td>设置 ASR 默认语言</td></tr>
            <tr><td><code>--set-workspace</code></td><td>设置工作目录</td></tr>
          </tbody>
        </table>

        <div class="note warning" style="margin-top: 3rem;">
          <div class="note-title">需要帮助？</div>
          <p>查看完整文档：<router-link to="/" style="color: var(--accent-cyan);">返回首页</router-link> | 使用 <code>opc &lt;command&gt; --help</code> 查看命令帮助</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const sidebarOpen = ref(false)

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

function scrollToSection(event) {
  event.preventDefault()
  const href = event.currentTarget.getAttribute('href')
  const target = document.querySelector(href)
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  // Close sidebar on mobile
  if (window.innerWidth <= 1024) {
    sidebarOpen.value = false
  }
}

// Scroll-based nav highlighting
function highlightNav() {
  const scrollPos = window.scrollY + 100
  const sections = document.querySelectorAll('h2[id]')
  const navItems = document.querySelectorAll('.nav-item')

  sections.forEach((section) => {
    const top = section.offsetTop
    const bottom = top + section.offsetHeight
    const id = section.getAttribute('id')

    if (scrollPos >= top && scrollPos < bottom) {
      navItems.forEach(item => item.classList.remove('active'))
      const activeItem = document.querySelector(`.nav-item a[href="#${id}"]`)
      if (activeItem) {
        activeItem.parentElement.classList.add('active')
      }
    }
  })
}

onMounted(() => {
  window.addEventListener('scroll', highlightNav)
  highlightNav()

  // Add click handlers to sidebar nav links
  document.querySelectorAll('.nav-item a[href^="#"]').forEach(link => {
    link.addEventListener('click', scrollToSection)
  })
})

onUnmounted(() => {
  window.removeEventListener('scroll', highlightNav)
})
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.docs-page {
  --bg-primary: #0a0a0f;
  --bg-secondary: #12121a;
  --bg-tertiary: #1a1a25;
  --bg-code: #0d0d12;
  --accent-cyan: #00f5d4;
  --accent-purple: #9b5de5;
  --accent-pink: #f15bb5;
  --accent-yellow: #fee440;
  --accent-orange: #ff6b35;
  --text-primary: #ffffff;
  --text-secondary: #a0a0b0;
  --text-muted: #606070;
  --border-color: #2a2a3a;
  --gradient-1: linear-gradient(135deg, #00f5d4 0%, #9b5de5 50%, #f15bb5 100%);
  font-family: 'Space Mono', monospace;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.7;
  overflow-x: hidden;
  min-height: 100vh;
}

.docs-page::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  opacity: 0.03;
  pointer-events: none;
  z-index: 1000;
}

/* Mobile Header */
.mobile-header {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  z-index: 200;
  padding: 0 1rem;
  align-items: center;
  justify-content: space-between;
}

.mobile-logo {
  font-family: 'Syne', sans-serif;
  font-size: 1.5rem;
  font-weight: 800;
  background: var(--gradient-1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.menu-toggle {
  width: 40px;
  height: 40px;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 1.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Layout */
.layout {
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 280px;
  height: 100vh;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  z-index: 100;
  padding: 2rem 0;
  transition: transform 0.3s ease;
}

.sidebar-header {
  padding: 0 1.5rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1.5rem;
}

.sidebar-logo {
  font-family: 'Syne', sans-serif;
  font-size: 1.75rem;
  font-weight: 800;
  background: var(--gradient-1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-decoration: none;
  display: inline-block;
  margin-bottom: 0.5rem;
}

.sidebar-version {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.nav-section {
  margin-bottom: 1.5rem;
}

.nav-title {
  padding: 0.5rem 1.5rem;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.nav-list {
  list-style: none;
}

.nav-item a {
  display: block;
  padding: 0.6rem 1.5rem;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.9rem;
  border-left: 3px solid transparent;
  transition: all 0.2s ease;
}

.nav-item a:hover {
  color: var(--text-primary);
  background: rgba(0, 245, 212, 0.05);
  border-left-color: var(--accent-cyan);
}

.nav-item.active a {
  color: var(--accent-cyan);
  background: rgba(0, 245, 212, 0.08);
  border-left-color: var(--accent-cyan);
}

.nav-item .command {
  font-family: 'Space Mono', monospace;
  font-size: 0.85rem;
}

.nav-item .desc {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
}

/* Main Content */
.main {
  margin-left: 280px;
  flex: 1;
  padding: 3rem 4rem;
  max-width: calc(100% - 280px);
}

/* Typography */
h1 {
  font-family: 'Syne', sans-serif;
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 1rem;
  letter-spacing: -0.02em;
  word-wrap: break-word;
}

h2 {
  font-family: 'Syne', sans-serif;
  font-size: 1.75rem;
  font-weight: 600;
  margin: 3rem 0 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
  word-wrap: break-word;
}

h3 {
  font-family: 'Syne', sans-serif;
  font-size: 1.25rem;
  font-weight: 600;
  margin: 2rem 0 1rem;
  color: var(--accent-cyan);
  word-wrap: break-word;
}

h4 {
  font-size: 1rem;
  font-weight: 700;
  margin: 1.5rem 0 0.75rem;
  color: var(--text-primary);
}

p {
  color: var(--text-secondary);
  margin-bottom: 1rem;
  word-wrap: break-word;
}

/* Code Blocks */
pre {
  background: var(--bg-code);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.25rem;
  overflow-x: auto;
  margin: 1rem 0;
  max-width: 100%;
}

code {
  font-family: 'Space Mono', monospace;
  font-size: 0.85rem;
  line-height: 1.6;
}

pre code {
  color: var(--text-primary);
}

:not(pre) > code {
  background: var(--bg-tertiary);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  color: var(--accent-cyan);
  font-size: 0.85em;
}

/* Syntax Highlighting */
.code-comment { color: var(--text-muted); }
.code-keyword { color: var(--accent-purple); }
.code-string { color: var(--accent-yellow); }
.code-flag { color: var(--accent-pink); }
.code-arg { color: var(--accent-cyan); }
.code-output { color: var(--text-secondary); }

/* Command Block */
.command-block {
  background: var(--bg-code);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  margin: 1.5rem 0;
  overflow: hidden;
  max-width: 100%;
}

.command-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.command-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.command-title {
  font-family: 'Syne', sans-serif;
  font-weight: 600;
  font-size: 0.95rem;
}

.command-body {
  padding: 1.25rem;
  overflow-x: auto;
}

.command-line {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.command-prompt {
  color: var(--accent-cyan);
  flex-shrink: 0;
}

.command-text {
  color: var(--text-primary);
  word-break: break-all;
}

.command-output {
  margin: 0.75rem 0 0.75rem 1.5rem;
  padding-left: 1rem;
  border-left: 2px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 0.85rem;
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  font-size: 0.9rem;
  display: block;
  overflow-x: auto;
}

th, td {
  padding: 0.875rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

th {
  font-weight: 600;
  color: var(--text-muted);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

tr:hover td {
  background: rgba(0, 245, 212, 0.03);
}

/* Tags */
.tag {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.tag-required {
  background: rgba(241, 91, 181, 0.15);
  color: var(--accent-pink);
}

.tag-optional {
  background: rgba(160, 160, 176, 0.15);
  color: var(--text-secondary);
}

.tag-engine {
  background: rgba(0, 245, 212, 0.15);
  color: var(--accent-cyan);
}

/* Parameter List */
.param-list {
  margin: 1rem 0;
}

.param-item {
  display: grid;
  grid-template-columns: minmax(150px, 200px) 1fr;
  gap: 1rem;
  padding: 1rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 0.75rem;
}

.param-name {
  font-family: 'Space Mono', monospace;
  font-size: 0.9rem;
  color: var(--accent-cyan);
  word-break: break-all;
}

.param-meta {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.param-desc {
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.param-default {
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-top: 0.5rem;
}

/* Example Cards */
.example-grid {
  display: grid;
  gap: 1rem;
  margin: 1.5rem 0;
}

.example-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}

.example-header {
  padding: 0.875rem 1.25rem;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.example-body {
  padding: 1.25rem;
  overflow-x: auto;
}

/* Notes */
.note {
  padding: 1rem 1.25rem;
  background: rgba(0, 245, 212, 0.05);
  border-left: 3px solid var(--accent-cyan);
  border-radius: 0 8px 8px 0;
  margin: 1.5rem 0;
}

.note-title {
  font-weight: 700;
  color: var(--accent-cyan);
  margin-bottom: 0.5rem;
}

.note p {
  margin: 0;
  font-size: 0.9rem;
}

.warning {
  background: rgba(255, 107, 53, 0.05);
  border-left-color: var(--accent-orange);
}

.warning .note-title {
  color: var(--accent-orange);
}

/* Pipeline Visual */
.pipeline-viz {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  margin: 1.5rem 0;
  padding: 1.5rem;
  background: var(--bg-secondary);
  border-radius: 12px;
  overflow-x: auto;
  gap: 0.5rem;
}

.pipeline-stage {
  flex-shrink: 0;
  text-align: center;
}

.stage-box {
  padding: 0.75rem 1rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 0.8rem;
  min-width: 100px;
}

.stage-box.active {
  border-color: var(--accent-cyan);
  background: rgba(0, 245, 212, 0.1);
}

.stage-arrow {
  color: var(--text-muted);
  font-size: 1.2rem;
  flex-shrink: 0;
}

.stage-output {
  font-size: 0.7rem;
  color: var(--accent-cyan);
  margin-top: 0.5rem;
}

/* Sidebar Overlay */
.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

.sidebar-overlay.active {
  display: block;
}

/* Responsive */
@media (max-width: 1024px) {
  .mobile-header {
    display: flex;
  }

  .sidebar {
    transform: translateX(-100%);
    top: 60px;
    height: calc(100vh - 60px);
    width: 260px;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .main {
    margin-left: 0;
    max-width: 100%;
    padding: 5rem 1.5rem 2rem;
  }

  h1 {
    font-size: 1.75rem;
  }

  h2 {
    font-size: 1.4rem;
  }

  h3 {
    font-size: 1.1rem;
  }

  .param-item {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .pipeline-viz {
    flex-wrap: wrap;
    justify-content: center;
  }

  .stage-arrow {
    display: none;
  }
}

@media (max-width: 640px) {
  .main {
    padding: 5rem 1rem 2rem;
  }

  pre {
    padding: 0.75rem;
  }

  .command-body {
    padding: 0.75rem;
  }

  .command-output {
    margin-left: 0.5rem;
    padding-left: 0.5rem;
  }

  th, td {
    padding: 0.625rem 0.75rem;
    font-size: 0.85rem;
  }
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--bg-primary);
}

::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--accent-cyan);
}
</style>
