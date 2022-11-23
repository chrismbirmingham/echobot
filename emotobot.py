from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from utils.whisper_stt import Transcriber
from utils.coqui_tts import Speak
import random


load_dotenv()
stt = Transcriber()
tts = Speak()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/scripts", StaticFiles(directory="scripts"), name="scripts")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def get(request: Request):
    return templates.TemplateResponse("emotobot_index.html", {
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
    response = pseudoparse(text)
    out = tts.synthesize_wav(response, speaker_id, style_wav)
    return StreamingResponse(out, media_type="audio/wav")


def make_random_choices(list_of_lists):
    r = []
    for l in list_of_lists:
        r.append(random.choice(l))
    return r

def pseudoparse(text):
    # returns a random guess 
    speech_classes = ["disclosure", "response", "meta"]
    disclosure_types = ["sharing", "proposing"]
    response_types = ["clarifying", "reacting"]
    emotions = ["happy", "angry", "sad", "worried", "excited"]


    speech_class, disclosure_type, response_type, emotion = make_random_choices([speech_classes, disclosure_types, response_types, emotions])

    if speech_class == "disclosure":
        start = "thank you"
        if disclosure_type == "sharing":
            middle = "for sharing that"

        elif disclosure_type == "proposing":
            middle = "for making that proposal"
        end = f"it sounds like you are feeling {emotion}. Does anyone have anything to respond to that?"
        response = " ".join([start, middle, end])

    if speech_class == "response":
        start = "thank you"
        if response_type == "clarifying":
            middle = "for following up"
        elif response_type == "reacting":
            middle = "for sharing your response"
        end = f"it sounds like you are feeling {emotion}. Does anyone have anything to respond to that?"
        response = " ".join([start, middle, end])
    if speech_class == "meta":
        response = "I don't have the capability to respond to that currently"
    return response

# def main():
#     app.run(debug=args.debug, host="::", port=args.port)


# if __name__ == "__main__":
#     main()