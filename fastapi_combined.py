#!flask/bin/python
import argparse
import io, os, sys, tempfile

from pathlib import Path
from typing import Union

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
from pydub import AudioSegment
import json
import asyncio
import logging
import whisper

# from TTS.config import load_config
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer




load_dotenv()
logger = logging.getLogger()


audio_model = whisper.load_model("large")
temp_dir = tempfile.mkdtemp()
save_path = os.path.join(temp_dir, "temp.wav")



def create_argparser():
    def convert_boolean(x):
        return x.lower() in ["true", "1", "yes"]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--list_models",
        type=convert_boolean,
        nargs="?",
        const=True,
        default=False,
        help="list available pre-trained tts and vocoder models.",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="tts_models/en/vctk/vits",
        help="Name of one of the pre-trained tts models in format <language>/<dataset>/<model_name>",
    )
    parser.add_argument("--vocoder_name", type=str, default=None, help="name of one of the released vocoder models.")

    # Args for running custom models
    parser.add_argument("--config_path", default=None, type=str, help="Path to model config file.")
    parser.add_argument(
        "--model_path",
        type=str,
        default=None,
        help="Path to model file.",
    )
    parser.add_argument(
        "--vocoder_path",
        type=str,
        help="Path to vocoder model file. If it is not defined, model uses GL as vocoder. Please make sure that you installed vocoder library before (WaveRNN).",
        default=None,
    )
    parser.add_argument("--vocoder_config_path", type=str, help="Path to vocoder model config file.", default=None)
    parser.add_argument("--speakers_file_path", type=str, help="JSON file for multi-speaker model.", default=None)
    parser.add_argument("--port", type=int, default=5002, help="port to listen on.")
    parser.add_argument("--use_cuda", type=convert_boolean, default=False, help="true to use CUDA.")
    parser.add_argument("--debug", type=convert_boolean, default=False, help="true to enable Flask debug mode.")
    parser.add_argument("--show_details", type=convert_boolean, default=False, help="Generate model detail page.")
    return parser


# parse the args
args, unknown = create_argparser().parse_known_args()

path = Path(__file__).parent / ".models.json"
manager = ModelManager(path)

if args.list_models:
    manager.list_models()
    sys.exit()

# update in-use models to the specified released models.
model_path, config_path, speakers_file_path, vocoder_path, vocoder_config_path = None, None, None, None, None

# CASE1: list pre-trained TTS models
if args.list_models:
    manager.list_models()
    sys.exit()

# CASE2: load pre-trained model paths
if args.model_name is not None and not args.model_path:
    model_path, config_path, model_item = manager.download_model(args.model_name)
    args.vocoder_name = model_item["default_vocoder"] if args.vocoder_name is None else args.vocoder_name

if args.vocoder_name is not None and not args.vocoder_path:
    vocoder_path, vocoder_config_path, _ = manager.download_model(args.vocoder_name)

# CASE3: set custom model paths
if args.model_path is not None:
    model_path = args.model_path
    config_path = args.config_path
    speakers_file_path = args.speakers_file_path

if args.vocoder_path is not None:
    vocoder_path = args.vocoder_path
    vocoder_config_path = args.vocoder_config_path

# load models
synthesizer = Synthesizer(
    tts_checkpoint=model_path,
    tts_config_path=config_path,
    tts_speakers_file=speakers_file_path,
    tts_languages_file=None,
    vocoder_checkpoint=vocoder_path,
    vocoder_config=vocoder_config_path,
    encoder_checkpoint="",
    encoder_config="",
    use_cuda=args.use_cuda,
)

use_multi_speaker = hasattr(synthesizer.tts_model, "num_speakers") and (
    synthesizer.tts_model.num_speakers > 1 or synthesizer.tts_speakers_file is not None
)

speaker_manager = getattr(synthesizer.tts_model, "speaker_manager", None)
# TODO: set this from SpeakerManager
use_gst = synthesizer.tts_config.get("use_gst", False)


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.autoescape = False

def style_wav_uri_to_dict(style_wav: str) -> Union[str, dict]:
    """Transform an uri style_wav, in either a string (path to wav file to be use for style transfer)
    or a dict (gst tokens/values to be use for styling)

    Args:
        style_wav (str): uri

    Returns:
        Union[str, dict]: path to file (str) or gst style (dict)
    """
    if style_wav:
        if os.path.isfile(style_wav) and style_wav.endswith(".wav"):
            return style_wav  # style_wav is a .wav file located on the server

        style_wav = json.loads(style_wav)
        return style_wav  # style_wav is a gst dictionary with {token1_id : token1_weigth, ...}
    return None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "use_multi_speaker":use_multi_speaker,
        "speaker_ids":speaker_manager.name_to_id if speaker_manager is not None else None,
    })



@app.get("/api/tts")
async def tts(request: Request, text: str, speaker_id: str = "", style_wav: str = ""):
    style_wav = style_wav_uri_to_dict(style_wav)
    print(" > Model input: {}".format(text))
    print(" > Speaker Idx: {}".format(speaker_id))
    wavs = synthesizer.tts(text, speaker_name=speaker_id, style_wav=style_wav)
    out = io.BytesIO()
    synthesizer.save_wav(wavs, out)
    return StreamingResponse(out, media_type="audio/wav")


@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    # Websocket to recieve the audio stream data
    await websocket.accept()

    rms_increase = .3
    stop_threshold = 1
    segment_ended = False
    segment_started = False
    stop_counter = 0
    data_collector = b''

    try:
        start = True
        while True:
            print("stop_counter: ", stop_counter, "segment_started: ", segment_started, "segment_ended: ", segment_ended)
            data = await websocket.receive_bytes()
            print("data recieved")

            if start:
                first_data = data
                data_bytes = io.BytesIO(first_data)
                audio_clip = AudioSegment.from_file(data_bytes, codec='opus')
                rms_threshold = audio_clip.rms * (1+rms_increase)
                print("RMS Threshold = ", rms_threshold)
                start=False
            else:
                data_sample = first_data + data

                data_bytes = io.BytesIO(data_sample)
                audio_clip = AudioSegment.from_file(data_bytes, codec='opus')
                print(audio_clip.rms, len(audio_clip), audio_clip.get_dc_offset())

                sample_rms = audio_clip.rms
                if sample_rms > rms_threshold and not segment_started:
                    print("starting segment")
                    segment_started = True
                    stop_counter = 0
                    data_collector = first_data

                if sample_rms < rms_threshold:
                    print("No speech detected")
                    if stop_counter > stop_threshold:
                        segment_ended = True
                    elif segment_started: 
                        stop_counter += 1
                

                if segment_started:
                    data_collector += data

            if segment_ended:
                data_bytes = io.BytesIO(data_collector)
                audio_clip = AudioSegment.from_file(data_bytes, codec='opus')
                print("Collected speech length: ", len(audio_clip))
                audio_clip.export(save_path, format="wav")
                result = audio_model.transcribe(save_path, language='english')
                await websocket.send_text(result["text"])
                segment_ended = False
                segment_started = False
                stop_counter = 0

    except Exception as e:
        raise Exception(f'Could not process audio: {e}')
    finally:
        await websocket.close()



def main():
    app.run(debug=args.debug, host="::", port=args.port)


if __name__ == "__main__":
    main()
