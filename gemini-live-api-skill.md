🛠️ Agent Skill: Gemini 3.1 Live API 全双工应用开发脚手架
1. 架构总览 (Architecture)
通信协议: 纯 WebSocket 全双工双向流 (WSS)，严禁使用 HTTP 轮询
。
前端端点: 原生 HTML5 + Web Audio API + MediaDevices API。
后端中间件: Python + FastAPI (Uvicorn) 异步处理。
AI SDK: 必须使用最新官方 SDK google-genai（严禁使用旧版 google-generativeai）
。
目标模型: gemini-3.1-flash-live-preview（专为低延迟、实时语音对话优化的模型）
。
2. 音视频数据规范 (Media Specifications)
AI 助手在处理代码时，必须严格遵守以下格式，否则 Gemini 会拒绝连接或引发内部崩溃：
音频输入 (前端 -> Gemini): 必须是 16kHz 采样率、单声道、16-bit PCM (little-endian) 格式
。
音频输出 (Gemini -> 前端): Gemini 吐出的是 24kHz 采样率、单声道、16-bit PCM
。前端必须使用 AudioBuffer 调度播放。
视频输入 (前端 -> Gemini): 必须抽帧为 JPEG 图片，频率最高为 1 FPS（每秒1帧），推荐分辨率 768x768，以 Base64 格式传输
。注意：提取 Base64 时必须去除 data:image/jpeg;base64, 前缀。
3. 🚨 核心避坑指南 (Critical API Traps & Solutions)
在生成代码时，AI 助手必须检查以下避坑清单（基于血泪排错经验）：
废弃参数陷阱：
不要在 config 中使用 enable_affective_dialog 或 proactive_audio，Gemini 3.1 Flash Live 暂不支持，会导致连接断开
。
将 thinking_budget（整数）替换为 thinking_level（枚举字符串："minimal", "low", "medium", "high"）
。对于低延迟对话，推荐默认使用 "minimal"
。
方法调用陷阱：
发送音视频流时，严禁使用 session.send()（这是纯文本用的）。必须使用专用的 session.send_realtime_input(audio=...) 或 video=...
。
必须显式声明需要音频返回：response_modalities=["AUDIO"]，并使用 v1beta 接口版本，否则会报 1011 Internal Error。
并发与任务守护陷阱：
在接收大模型语音的 receive_from_gemini 任务中，session.receive() 必须包裹在 while True: 循环中。因为 Gemini 在遇到打断（Interruption）或一轮话说完时会自动结束当前 receive 迭代，没有外层循环会导致 WebSocket 被后端当做任务完成而主动关闭。
打断与回声消除 (VAD & Echo Cancellation)：
前端 getUserMedia 必须显式开启 echoCancellation: true, noiseSuppression: true, autoGainControl: true
。
当后端接收到 server_content.interrupted == True 时，必须立即通过 WebSocket 通知前端清空并停止当前正在播放的所有 Audio 队列
。
4. 核心代码模板 (Boilerplate Reference)
4.1 FastAPI 后端核心连接逻辑
client = genai.Client(http_options={"api_version": "v1beta"})
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(parts=[types.Part.from_text(text="你的系统提示词")]),
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Leda") # 推荐声音: Leda, Puck, Aoede [21, 22]
        )
    )
)

async with client.aio.live.connect(model="gemini-3.1-flash-live-preview", config=config) as session:
    # 接收客户端流并发送给 Gemini (使用 send_realtime_input)
    async def receive_from_client():
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    await session.send_realtime_input(audio={"data": message["bytes"], "mime_type": "audio/pcm;rate=16000"})
                elif "text" in message:
                    # 处理 JSON 格式的 1FPS 视频 Base64 帧
                    payload = json.loads(message["text"])
                    img_bytes = base64.b64decode(payload["data"])
                    await session.send_realtime_input(video={"data": img_bytes, "mime_type": "image/jpeg"})
        except (WebSocketDisconnect, RuntimeError):
            pass # 客户端主动挂断

    # 接收 Gemini 流并下发给客户端 (必须加 while True)
    async def receive_from_gemini():
        while True: 
            try:
                async for response in session.receive():
                    server_content = response.server_content
                    if server_content is not None:
                        # 透传打断信号
                        if getattr(server_content, "interrupted", False):
                            await websocket.send_text("interrupted")
                        
                        # 透传 24kHz PCM 音频数据
                        if server_content.model_turn is not None:
                            for part in server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    await websocket.send_bytes(part.inline_data.data)
            except asyncio.CancelledError:
                break
4.2 前端音频调度核心逻辑 (Audio Scheduler)
// 避免声音重叠的核心队列管理器
let playContext = new AudioContext({ sampleRate: 24000 }); // 匹配 Gemini 24kHz 输出
let nextPlayTime = playContext.currentTime;
let activeSources = [];

socket.onmessage = async (event) => {
    // 处理打断信号
    if (typeof event.data === "string" && event.data === "interrupted") {
        activeSources.forEach(source => { try { source.stop(); } catch (e) {} });
        activeSources = [];
        nextPlayTime = playContext.currentTime;
        return;
    }

    // PCM 播放调度
    const pcmData = new Int16Array(event.data);
    const floatData = new Float32Array(pcmData.length);
    for (let i = 0; i < pcmData.length; i++) floatData[i] = pcmData[i] / 32768;
    
    const audioBuffer = playContext.createBuffer(1, floatData.length, 24000);
    audioBuffer.getChannelData(0).set(floatData);
    
    const playSource = playContext.createBufferSource();
    playSource.buffer = audioBuffer;
    playSource.connect(playContext.destination);
    
    if (nextPlayTime < playContext.currentTime) nextPlayTime = playContext.currentTime;
    playSource.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;
    
    activeSources.push(playSource);
};
5. 项目工程化规范
环境变量管理：所有关键配置（GEMINI_API_KEY、GEMINI_MODEL、SERVER_PORT 及业务 PROMPT）提取到 .env 文件。
Docker 部署：Dockerfile 中 CMD 应直接设置后端应用端口，例如 CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]。
日志输出：Docker 环境中必须配置 PYTHONUNBUFFERED=1 以防止日志截断，这是排错的生命线。
