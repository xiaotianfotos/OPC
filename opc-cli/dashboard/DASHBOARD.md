# OPC Dashboard

技能注册式架构的管理面板

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    OPC Dashboard (Node.js)                  │
│              Port: 12080 (configurable)                     │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Vue3 Frontend  │  │         Express API             │   │
│  │  - /            │  │  - GET  /api/skills             │   │
│  │  - /skill/cut   │  │  - GET  /api/skill/cut/status   │   │
│  │                 │  │  - POST /api/skill/cut/init     │   │
│  │                 │  │  - POST /api/skill/cut/stop     │   │
│  └────────┬────────┘  └─────────────┬───────────────────┘   │
│           │                        │                         │
│           │                        │ spawn uv run            │
│           │                        ▼                         │
│  ┌────────▼─────────────────────────────────────────────┐   │
│  │  iframe (http://localhost:12082)                     │   │
│  │  ┌───────────────────────────────────────────────┐   │   │
│  │  │  Cut Server (Flask)                           │   │   │
│  │  │  - ASR 字词级时间戳解析                        │   │   │
│  │  │  - 视频剪辑界面                                │   │   │
│  │  └───────────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 配置

配置文件位于 `~/.opc_cli/opc/config.json`

### 配置项

| 键 | 默认值 | 说明 |
|---|---|---|
| `dashboard_host` | `0.0.0.0` | Dashboard 服务器监听地址 |
| `dashboard_port` | `12080` | Dashboard 服务器端口 |
| `cut_server_port` | `12082` | Cut 技能服务器默认端口 |
| `workspace_dir` | `~/opc-workspace` | ASR/Cut 工作目录 |

### 设置配置

```bash
# 设置 Dashboard 端口
opc config --set-dashboard-port 12080

# 设置 Dashboard 监听地址（允许远程访问）
opc config --set-dashboard-host 0.0.0.0

# 设置 Cut 服务器端口
opc config --set-cut-server-port 12082

# 设置工作目录
opc config --set-workspace /path/to/workspace

# 查看所有配置
opc config --show
```

### 远程访问

如果需要从远程机器访问 Dashboard，设置 `dashboard_host` 为 `0.0.0.0`：

```bash
opc config --set-dashboard-host 0.0.0.0
opc config --set-dashboard-port 12080
```

然后从远程机器访问 `http://<your-ip>:12080`

## 启动方式

### 1. 启动 Dashboard 服务器

```bash
cd /vol2/1000/work/skills/opc-cli/dashboard/server
node server-prod.js
```

Dashboard 将在配置指定的地址和端口启动（默认 http://0.0.0.0:12080）

### 2. 访问 Dashboard

- 首页：http://localhost:12080/
- Cut 编辑器：http://localhost:12080/skill/cut/editor

### 3. 启动 Cut 服务

通过 Dashboard 首页的表单：
- 视频文件路径：输入视频文件路径
- ASR JSON 文件 (可选)：输入 ASR 生成的 JSON 文件路径
- 点击"启动剪辑服务"

或通过 API：

```bash
curl -X POST http://localhost:12080/api/skill/cut/init \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/video.mp4",
    "json": "/path/to/result.json",
    "port": 12082
  }'
```

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/skills | 获取所有技能列表 |
| GET | /api/skill/cut/status | 获取 Cut 技能状态 |
| POST | /api/skill/cut/init | 初始化 Cut 技能 |
| POST | /api/skill/cut/stop | 停止 Cut 技能 |

## 前端构建

```bash
cd /vol2/1000/work/skills/opc-skill/dashboard/server
npm install
npm run build
```

## 添加新技能

1. 在 `server-prod.js` 中添加技能状态：

```javascript
const skillState = {
  cut: { ... },
  newSkill: { status: 'idle', ... }
};
```

2. 添加 API 端点：

```javascript
app.post('/api/skill/newSkill/init', async (req, res) => {
  // 启动技能服务器
});
```

3. 在 `Home.vue` 中添加技能卡片和启动表单

4. 创建技能编辑器视图 `src/views/NewSkillEditor.vue`

5. 在 `main.js` 中添加路由

## 技术栈

- **后端**: Node.js + Express
- **前端**: Vue 3 + Vue Router + Vite
- **技能服务器**: Python + Flask
- **进程管理**: uv (Python 包管理)
