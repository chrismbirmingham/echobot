function onoff(){
    currentvalue = document.getElementById('onoff').value;
    if(currentvalue == "Listening"){
        document.getElementById("onoff").value="Click to Listen";
    }else{
        document.getElementById("onoff").value="Listening";
    }
}
function getTextValue(textId) {
    const container = q(textId)
    if (container) {
        return container.value
    }
    return ""
}

function q(selector) { return document.querySelector(selector) }

q('#text').focus()

function do_tts(e) {
    const text = q('#text').value
    const speaker_id = getTextValue('#speaker_id')
    const style_wav = getTextValue('#style_wav')
    if (text) {
        q('#message').textContent = 'Synthesizing...'
        q('#speak-button').disabled = true
        q('#audio').hidden = true
        respond_to(text, speaker_id, style_wav)
    }
    e.preventDefault()
    return false
}
q('#audio').addEventListener("ended", function(){
    q('#audio').currentTime = 0;
    console.log("ended");
    document.getElementById("onoff").value="Listening";
});
q('#speak-button').addEventListener('click', do_tts)

q('#text').addEventListener('keyup', function (e) {
    if (e.keyCode == 13) { // enter
        do_tts(e)
    }
})

function respond_to(text, speaker_id = "", style_wav = "") {
    document.getElementById('onoff').value = "Click to Listen"
    fetch(`/api/tts?text=${encodeURIComponent(text)}&speaker_id=${encodeURIComponent(speaker_id)}&style_wav=${encodeURIComponent(style_wav)}`, { cache: 'no-cache' })
        .then(function (res) {
            if (!res.ok) throw Error(res.statusText)
            return res.blob()
        }).then(function (blob) {
            q('#message').textContent = ''
            q('#speak-button').disabled = false
            q('#audio').src = URL.createObjectURL(blob)
            q('#audio').hidden = false
        }).catch(function (err) {
            q('#message').textContent = 'Error: ' + err.message
            q('#speak-button').disabled = false
        })
    
}


navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    if (!MediaRecorder.isTypeSupported('audio/webm'))
        return alert('Browser not supported')

    const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm',
    })

    const socket = new WebSocket('ws://localhost:8000/listen')

    socket.onopen = () => {
        q('#status').textContent = 'Connected'
        console.log({ event: 'onopen' })
        mediaRecorder.addEventListener('dataavailable', async (event) => {
            if (event.data.size > 0 && socket.readyState == 1 && document.getElementById('onoff').value == "Listening") {
                socket.send(event.data)
            }
    })
    mediaRecorder.start(250)
    }

    socket.onmessage = (message) => {
        const received = message.data
        if (received) {
            console.log(received)
            document.querySelector('#transcript').innerHTML += ' <br>' + received
            const speaker_id = getTextValue('#speaker_id')
            const style_wav = getTextValue('#style_wav')
            respond_to(received, speaker_id, style_wav)
        }
    }

    socket.onclose = () => {
        console.log({ event: 'onclose' })
    }

    socket.onerror = (error) => {
        console.log({ event: 'onerror', error })
    }

})