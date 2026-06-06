import asyncio
import os
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
VOICE_NAME = os.environ.get("GEMINI_VOICE", "Leda")
AUDIO_PROMPT = os.environ.get("AUDIO_PROMPT", "你好，请作为一个友好的邻家姐姐和孩子聊天。")
VIDEO_PROMPT = os.environ.get("VIDEO_PROMPT", "你好，请作为一个科学老师，看着画面回答孩子的问题。")

app = FastAPI()

# 允许跨域，未来开发小程序或 APK 时必须依赖此项
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 提供可视化前端页面服务
@app.get("/")
async def get_frontend():
    return FileResponse("index.html")

# WebSocket API 接口，供前端/App/小程序连接
@app.websocket("/ws/{mode}")
async def websocket_endpoint(websocket: WebSocket, mode: str):
    await websocket.accept()
    if not API_KEY:
        print("❌ 未找到 GEMINI_API_KEY，请检查 .env 文件！")
        await websocket.close()
        return

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
        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if "bytes" in message:
                            # 发送16kHz PCM 音频流
                            await session.send_realtime_input(audio={"data": message["bytes"], "mime_type": "audio/pcm;rate=16000"})
                        elif "text" in message:
                            try:
                                payload = json.loads(message["text"])
                                if payload.get("type") == "video":
                                    img_bytes = base64.b64decode(payload["data"])
                                    # 发送 JPEG 视频帧
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
                                # 感知模型打断信号
                                if getattr(server_content, "interrupted", False):
                                    await websocket.send_text("interrupted")
                                
                                # Gemini 3.1 会将所有内容部分放在同一个事件中，需遍历发送
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
