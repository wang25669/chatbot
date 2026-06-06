# 🌟 AI 智能玩伴 (Gemini Live 双模守护)

这是一个基于 Google Gemini Live API 构建的全双工、低延迟儿童语音伴读项目。它无需复杂的传统前端架构，直接通过浏览器与 AI 建立双向流媒体 (WebSockets) 对话。

项目包含两种独立模式，为小朋友提供更丰富的陪伴：
1. 📞 **语音通话模式（邻家大姐姐）**：纯语音互动，模拟真实通电话体验（单次最大限制 15 分钟）。
2. 📷 **视频探索模式（科学老师）**：调用手机后置摄像头，AI 能够“看到”真实的物理世界，化身科学小老师解答孩子的观察疑问（单次最大限制 2 分钟）。

## 🎯 核心能力与架构

*   **双模式动态路由**：支持纯语音通讯（邻家大姐姐）和后置摄像头视频伴读（科学小老师）。
*   **前后端解耦 (Server-to-Server)**：Python (FastAPI) 仅作为 WebSockets 中间代理，向前端提供 `index.html` 的同时暴露 `/ws/audio` 和 `/ws/video` 接口。未来可无缝对接 Android APK、微信小程序、智能机器人等客户端。
*   **高级 Prompt 工程**：引入了 Director's Notes（导演笔记）与隐蔽音频标签（如 `[giggles]`），强制 AI 控制情感和语速，消除机械感。

## 📁 目录结构
```text
.
├── .env                  # 动态配置文件（API Key，自定义 Prompt，端口等）
├── docker-compose.yml    # Docker 容器编排文件 (当前配置为本地 Build 模式)
├── Dockerfile            # 环境构建及静态资源打包脚本
├── main.py               # FastAPI 后端核心 (跨域 WebSocket 引擎)
├── index.html            # 独立抽离的前端测试面板 (自动映射宿主 IP)
└── requirements.txt      # Python SDK 依赖

##🛠️ 如何配置 (.env)
项目的所有动态参数均已提取至 .env 文件中。启动前，请确保在根目录创建了 .env 并填入以下核心内容：
GEMINI_API_KEY：你在 Google AI Studio 申请的 API Key。
GEMINI_MODEL：支持 Live API 的模型名称，目前推荐 gemini-3.1-flash-live-preview。
GEMINI_VOICE：声音预设。给孩子使用推荐以下几种：
  Leda (年轻活力)
  Puck (欢快)
  Callirrhoe (随和)
  Vindemiatrix (极其温柔)
AUDIO_PROMPT / VIDEO_PROMPT：
你可以随时在 .env 中修改这两种模式的指导提示词（Prompt）。

##🚀 本地部署测试
配置环境变量：在项目根目录编辑 .env 文件，填入你的 GEMINI_API_KEY。
启动构建：docker compose up -d
开始体验：
必须在局域网 HTTPS 环境或 localhost 下访问（例如 http://127.0.0.1:8000 或利用内网穿透 / 反向代理生成的安全链接），否则手机浏览器无法获取麦克风和摄像头权限。
点击对应的通话模式即可开始双向全双工对话！

##📱 使用指南与网络要求
在服务器启动成功后，网页服务将默认监听 8000 端口。

##⚠️ 极其重要 (HTTPS 要求)：
现代手机浏览器（如 iOS Safari 或 Android Chrome）出于隐私安全，仅允许在 HTTPS 环境下或 localhost 环境下调用摄像头和麦克风。
如果你需要用手机连接局域网中的服务器，请务必使用 OpenResty / Nginx 配合反向代理配置 HTTPS 证书，或使用 ngrok 进行内网穿透（如 ngrok http 8000 生成 https 链接）。
用手机浏览器打开配置好的 HTTPS 地址，即可看到选择界面。
视频模式提示：点击“视频探索”后，程序会自动申请并唤起手机的后置摄像头，以 1 FPS 的频率抓取画面给大模型分析，同时保持全双工的语音对话交流。
