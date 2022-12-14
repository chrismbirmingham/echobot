# echobot
Super simple voice chatbot through a basic web interface


## Live/Local STT and TTS
Simple server with FastAPI  
STT through the whisper model  
TTS through coqui TTS  
Artwork from DALLE

To run this project create a virtual environment by running the below commands. 

```
mkdir [% NAME_OF_YOUR_DIRECTORY %]
cd [% NAME_OF_YOUR_DIRECTORY %]
python3 -m venv venv
source venv/bin/activate
```

Make sure your virtual environment is activated and install the dependencies in the requirements.txt file inside. 

```
pip install -r requirements.txt
```

Make sure you're in the directory with the **main.py** file and run the project in the development server.

```
uvicorn echobot:app --reload
```

Pull up a browser and go to your localhost, http://127.0.0.1:8000/.

Allow access to your microphone and start speaking. A transcript of your audio will appear in the browser. 

Note the microphone noise threshold can be tuned by changing the rms_increase parameter in echobot.py

