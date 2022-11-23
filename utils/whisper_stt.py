import whisper
import os, io
import tempfile
from pydub import AudioSegment




class Transcriber():
    """ 
    Helper Class which processes audio into a single utterance and returns the transcription
    """
    def __init__(self, rms_increase: float = .3, stop_threshold: int = 2, model_size: str="medium") -> None:
        self.rms_increase = rms_increase
        self.stop_threshold = stop_threshold
        self.segment_ended = False
        self.segment_started = False
        self.stop_counter = 0
        self.data_collector = b''
        self.save_path = os.path.join(tempfile.mkdtemp(), "temp.wav")

        self.audio_model = whisper.load_model(model_size)

    def _process_bytes(self, data):

        data_bytes = io.BytesIO(data)
        audio_clip = AudioSegment.from_file(data_bytes, codec='opus')
        return audio_clip

    def process_first_data(self, data):
        self.first_data = data
        audio_clip = self._process_bytes(data)
        self.rms_threshold = audio_clip.rms * (1+self.rms_increase)
        print("RMS Threshold = ", self.rms_threshold)

    def process_data(self, data):
        data_sample = self.first_data + data
        audio_clip = self._process_bytes(data_sample)
        print(audio_clip.rms, len(audio_clip), audio_clip.get_dc_offset())

        current_sample_rms = audio_clip.rms
        if current_sample_rms > self.rms_threshold and not self.segment_started:
            print("starting segment")
            self.segment_started = True
            self.stop_counter = 0
            self.data_collector = self.first_data

        if current_sample_rms < self.rms_threshold:
            print("No speech detected")
            if self.stop_counter > self.stop_threshold:
                self.segment_ended = True
            elif self.segment_started: 
                self.stop_counter += 1

        if self.segment_started:
            self.data_collector += data

    def transcribe(self):
        audio_clip = self._process_bytes(self.data_collector)
        print("Collected speech length: ", len(audio_clip))

        audio_clip.export(self.save_path, format="wav")
        result = self.audio_model.transcribe(self.save_path, language='english')

        self.segment_ended = False
        self.segment_started = False
        self.stop_counter = 0

        return result["text"]