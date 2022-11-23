from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from utils.whisper_stt import Transcriber
from utils.coqui_tts import Speak
import random


#TODO Move to a file:
my_file = open("buddhaquotes.txt", "r")
data = my_file.read()
sayings = data.split("\n")
# print(sayings)

load_dotenv()
stt = Transcriber()
tts = Speak()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def get(request: Request):
    return templates.TemplateResponse("buddhabot_index.html", {
        "request": request, 
        "use_multi_speaker":tts.use_multi_speaker,
        "speaker_ids":tts.speaker_ids,
    })

@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    # Websocket to recieve the audio stream data
    await websocket.accept()

    try:
        start = True
        while True:
            data = await websocket.receive_bytes()
            print("data recieved")

            if start:
                stt.process_first_data(data)
                start=False
            else:
                stt.process_data(data)


            if stt.segment_ended:
                await websocket.send_text(stt.transcribe())

    except Exception as e:
        raise Exception(f'Could not process audio: {e}')
    finally:
        await websocket.close()

@app.get("/api/tts")
def text_to_speech(text: str, speaker_id: str = "", style_wav: str = ""):
    text = random.choice(sayings)

    out = tts.synthesize_wav(text, speaker_id, style_wav)
    return StreamingResponse(out, media_type="audio/wav")


# def main():
#     app.run(debug=args.debug, host="::", port=args.port)


# if __name__ == "__main__":
#     main()