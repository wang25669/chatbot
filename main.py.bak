import asyncio
import os
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types

# 读取环境变量（由 docker-compose 的 env_file 自动注入）
API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
VOICE_NAME = os.environ.get("GEMINI_VOICE", "Leda")
AUDIO_PROMPT = os.environ.get("AUDIO_PROMPT", "你好，请作为一个友好的邻家姐姐和孩子聊天。")
VIDEO_PROMPT = os.environ.get("VIDEO_PROMPT", "你好，请作为自然科学老师，看着画面回答孩子的问题。")

app = FastAPI()

# ==========================================
# 整合版前端 HTML (保持不变，已修复 Base64 截取 BUG)
# ==========================================
html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 智能玩伴</title>
    <style>
        body { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif; background-color: #fdf6e3; margin: 0;}
        h1 { color: #d9777f; margin-bottom: 10px;}
        #videoContainer { position: relative; width: 90%; max-width: 400px; border-radius: 20px; overflow: hidden; box-shadow: 0 8px 16px rgba(0,0,0,0.1); margin-bottom: 20px; display: none;}
        video { width: 100%; display: block; background-color: #000; }
        .btn-group { display: flex; gap: 15px; margin-bottom: 15px; }
        button { padding: 18px 24px; font-size: 18px; border-radius: 50px; border: none; color: white; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-weight: bold;}
        #audioBtn { background-color: #d9777f; }
        #videoBtn { background-color: #5c9b74; }
        #stopBtn { background-color: #e74c3c; display: none; width: 80%; max-width: 300px; }
        button:disabled { background-color: #ccc; cursor: not-allowed; }
        #status { margin-top: 15px; font-size: 16px; color: #555;}
        canvas { display: none; }
    </style>
</head>
<body>
    <h1 id="titleText">👧 邻家大姐姐</h1>
    
    <div id="videoContainer">
        <video id="cameraFeed" autoplay playsinline muted></video>
    </div>

    <div class="btn-group" id="startButtons">
        <button id="audioBtn">📞 语音通话</button>
        <button id="videoBtn">📷 视频探索</button>
    </div>
    
    <button id="stopBtn">挂断</button>
    
    <div id="status">请选择一种互动方式...</div>
    <canvas id="canvasElement"></canvas>

    <script>
        let socket;
        let audioContext;
        let processor;
        let mediaStream;
        let playContext;
        let videoInterval;
        
        let nextPlayTime = 0;
        let activeSources = [];
        let currentMode = null;

        const audioBtn = document.getElementById('audioBtn');
        const videoBtn = document.getElementById('videoBtn');
        const stopBtn = document.getElementById('stopBtn');
        const status = document.getElementById('status');
        const videoContainer = document.getElementById('videoContainer');
        const video = document.getElementById('cameraFeed');
        const canvas = document.getElementById('canvasElement');
        const ctx = canvas.getContext('2d');
        const titleText = document.getElementById('titleText');

        audioBtn.onclick = () => startSession('audio');
        videoBtn.onclick = () => startSession('video');
        stopBtn.onclick = () => stopConversation();

        function stopAllAudio() {
            activeSources.forEach(source => {
                try { source.stop(); } catch (e) {}
            });
            activeSources = [];
            if (playContext) {
                nextPlayTime = playContext.currentTime; 
            }
        }

        async function startSession(mode) {
            currentMode = mode;
            audioBtn.disabled = true;
            videoBtn.disabled = true;
            status.innerText = "正在连接...";
            
            document.getElementById('startButtons').style.display = 'none';
            stopBtn.style.display = 'block';

            try {
                const constraints = {
                    audio: { sampleRate: 16000, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                };

                if (mode === 'video') {
                    constraints.video = { facingMode: "environment", width: { ideal: 768 }, height: { ideal: 768 } };
                    videoContainer.style.display = 'block';
                    titleText.innerText = "🌿 自然科学小老师";
                } else {
                    titleText.innerText = "👧 邻家大姐姐";
                }

                mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
                
                if (mode === 'video') {
                    video.srcObject = mediaStream;
                }

                audioContext = new AudioContext({ sampleRate: 16000 });
                const source = audioContext.createMediaStreamSource(mediaStream);
                processor = audioContext.createScriptProcessor(2048, 1, 1);
                source.connect(processor);
                processor.connect(audioContext.destination);
                
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                socket = new WebSocket(`${protocol}//${window.location.host}/ws/${mode}`);
                socket.binaryType = 'arraybuffer';

                socket.onopen = () => {
                    status.innerText = mode === 'video' ? "🟢 镜头已开启，2分钟探索时间！" : "🟢 通话中，可以说话啦！";
                    
                    if (mode === 'video') {
                        videoInterval = setInterval(() => {
                            if (socket.readyState === WebSocket.OPEN && video.readyState === video.HAVE_ENOUGH_DATA) {
                                canvas.width = video.videoWidth;
                                canvas.height = video.videoHeight;
                                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                                // 【已修复】确保只提取纯图片 Base64 数据
                                const base64Data = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
                                socket.send(JSON.stringify({ type: "video", data: base64Data }));
                            }
                        }, 1000); 
                    }
                };

                processor.onaudioprocess = (e) => {
                    if (socket.readyState === WebSocket.OPEN) {
                        const inputData = e.inputBuffer.getChannelData(0);
                        const pcmData = new Int16Array(inputData.length);
                        for (let i = 0; i < inputData.length; i++) {
                            pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                        }
                        socket.send(pcmData.buffer);
                    }
                };

                playContext = new AudioContext({ sampleRate: 24000 });
                nextPlayTime = playContext.currentTime;

                socket.onmessage = async (event) => {
                    if (typeof event.data === "string") {
                        if (event.data === "interrupted") {
                            stopAllAudio();
                        }
                        return;
                    }

                    const pcmData = new Int16Array(event.data);
                    const floatData = new Float32Array(pcmData.length);
                    for (let i = 0; i < pcmData.length; i++) {
                        floatData[i] = pcmData[i] / 32768;
                    }
                    const audioBuffer = playContext.createBuffer(1, floatData.length, 24000);
                    audioBuffer.getChannelData(0).set(floatData);
                    
                    const playSource = playContext.createBufferSource();
                    playSource.buffer = audioBuffer;
                    playSource.connect(playContext.destination);
                    
                    const currentTime = playContext.currentTime;
                    if (nextPlayTime < currentTime) {
                        nextPlayTime = currentTime;
                    }
                    
                    playSource.start(nextPlayTime);
                    nextPlayTime += audioBuffer.duration;

                    playSource.onended = () => {
                        const index = activeSources.indexOf(playSource);
                        if (index > -1) activeSources.splice(index, 1);
                    };
                    activeSources.push(playSource);
                };

                socket.onclose = () => {
                    if (status.innerText !== "已挂断") stopConversation(true);
                };

            } catch (err) {
                status.innerText = "❌ 硬件访问失败，请检查浏览器权限。";
                resetUI();
            }
        }

        function stopConversation(autoDisconnect = false) {
            if (socket) socket.close();
            if (processor) processor.disconnect();
            if (audioContext) audioContext.close();
            if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
            if (videoInterval) clearInterval(videoInterval);
            stopAllAudio();
            if (playContext) playContext.close();
            
            video.srcObject = null;
            status.innerText = autoDisconnect ? "⏱️ 会话结束或连接断开" : "已挂断";
            resetUI();
        }

        function resetUI() {
            videoContainer.style.display = 'none';
            document.getElementById('startButtons').style.display = 'flex';
            stopBtn.style.display = 'none';
            audioBtn.disabled = false;
            videoBtn.disabled = false;
            titleText.innerText = "👧 邻家大姐姐";
        }
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content)

@app.websocket("/ws/{mode}")
async def websocket_endpoint(websocket: WebSocket, mode: str):
    await websocket.accept()
    if not API_KEY:
        print("❌ 未找到 GEMINI_API_KEY，请检查 .env 文件！")
        await websocket.close()
        return

    # 动态匹配前端传来的 Prompt 模式
    current_prompt = VIDEO_PROMPT if mode == "video" else AUDIO_PROMPT

    client = genai.Client(http_options={"api_version": "v1beta"})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text=current_prompt)]),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        )
    )

    try:
        # 使用 env 中配置的模型
        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if "bytes" in message:
                            await session.send_realtime_input(audio={"data": message["bytes"], "mime_type": "audio/pcm;rate=16000"})
                        elif "text" in message:
                            try:
                                payload = json.loads(message["text"])
                                if payload.get("type") == "video":
                                    img_bytes = base64.b64decode(payload["data"])
                                    await session.send_realtime_input(video={"data": img_bytes, "mime_type": "image/jpeg"})
                            except Exception as e:
                                print(f"⚠️ 视频帧解析或发送失败: {e}")
                except (WebSocketDisconnect, RuntimeError):
                    print(f"ℹ️ {mode} 模式客户端已主动挂断")

            async def receive_from_gemini():
                while True: 
                    try:
                        async for response in session.receive():
                            server_content = response.server_content
                            if server_content is not None:
                                if getattr(server_content, "interrupted", False):
                                    await websocket.send_text("interrupted")
                                
                                if server_content.model_turn is not None:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            await websocket.send_bytes(part.inline_data.data)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        print(f"⚠️ Gemini接收循环抛出异常: {e}")
                        break

            client_task = asyncio.create_task(receive_from_client())
            gemini_task = asyncio.create_task(receive_from_gemini())

            done, pending = await asyncio.wait(
                [client_task, gemini_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

    except Exception as e:
        print(f"❌ 内部会话断开: {e}")
    finally:
        if websocket.client_state == 1:
            await websocket.close()
