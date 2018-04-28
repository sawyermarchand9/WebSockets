from ws4py.client.threadedclient import WebSocketClient
import base64, json, ssl, subprocess, threading, time
from subprocess import Popen, STDOUT
import os
# These are from the Audio Example
import pyaudio
import time
import wave
# for requesting information
import requests



# open stream
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 2000  # was 2048, made this 2000 to divide evenly into 16000, smoothed out the playback
command = "cmd"

# https://2001archive.org/      Open audio files
wf_greeting = wave.open('361927__robert-twent__hello.wav', 'rb')
wf_goodbye = wave.open('102003__robinhood76__01887-goodbye-spell.wav', 'rb')
wf_ignore = wave.open('351873__balloonhead__02-objection-ignored.wav', 'rb')
Command_State = None


'''
Port Audio seems to have some known issues.
'''


def play_uncompressed_wave(wave_object):
    # define callback (2)
    def callback(in_data, frame_count, time_info, status):
        data = wave_object.readframes(frame_count)
        return data, pyaudio.paContinue

    # instantiate PyAudio (1)
    p_out = pyaudio.PyAudio()

    stream_out = p_out.open(format=p_out.get_format_from_width(wave_object.getsampwidth()),
                            channels=wave_object.getnchannels(),
                            rate=wave_object.getframerate(),
                            output=True,
                            stream_callback=callback)

    # start the stream (4)
    stream_out.start_stream()

    # wait for stream to finish (5)
    while stream_out.is_active():
        time.sleep(0.1)

    # stop stream (6)
    stream_out.stop_stream()
    stream_out.close()
    wave_object.close()
    p_out.terminate()
    pass


class SpeechToTextClient(WebSocketClient):
    def __init__(self):
        # watson url speech to text
        ws_url = "wss://stream.watsonplatform.net/speech-to-text/api/v1/recognize"

        # username and password
        username = "{username}"
        password = "{password}"

        # authorize string
        authstring = "{0}:{1}".format(username, password)

        base64string = base64.b64encode(authstring.encode('utf-8')).decode('utf-8')

        self.listening = False
        self.empty_count = 0
        self.Gathered_String = ''
        self.stream_audio_thread = threading.Thread(target=self.stream_audio)
        try:
            WebSocketClient.__init__(self, ws_url,
                                     headers=[("Authorization", "Basic %s" % base64string)])
            self.connect()
        except:
            print("Failed to open WebSocket.")

    def opened(self):
        self.send('{"action": "start", "content-type": "audio/l16;rate=16000"}')
        self.stream_audio_thread.start()

    def received_message(self, message):
        global Command_State
        message = json.loads(str(message))
        print(message)

        if "state" in message:
            if message["state"] == "listening" and Command_State is None:
                # play_uncompressed_wave(wf_greeting)
                self.listening = True
        if "results" in message:
            print(Command_State)
            if message["results"]:
                x = message['results']
                print(x, 'x')

                if x[0]['alternatives'][0]['transcript'] == 'Watson ' and Command_State is None:
                    print("found a command")
                    play_uncompressed_wave(wf_greeting)
                    Command_State = 'Started'

                if x[0]['alternatives'][0]['transcript'] == 'ignore ' and Command_State is 'Started':
                    play_uncompressed_wave(wf_ignore)
                    Command_State = None
                    self.listening = True

                if x[0]['alternatives'][0]['transcript'] == 'translate ' and Command_State is 'Started':
                    Command_State = 'Gather'
                    self.Gathered_String = ''
                    self.listening = True
                    self.empty_count = 0

                if x[0]['alternatives'][0]['transcript'] == 'quit ' and Command_State is 'Started':
                    self.listening = False
                    play_uncompressed_wave(wf_goodbye)
                    Command_State = 'Exit'
                    self.stream_audio_thread.join()

                if x[0]['alternatives'][0]['transcript'] == 'open ' and Command_State is 'Started':
                    os.startfile('C:\Program Files\Sublime Text 3\sublime_text', 'open')
                    pass

                if Command_State == 'Gather':
                    self.Gathered_String = self.Gathered_String + x[0]['alternatives'][0]['transcript']
                    # print(x[0]['alternatives'][0]['transcript'])
                    # if self.Gathered_String == 'hello Watson ':
                    #     # os.startfile('C:\Program Files\Blender Foundation\Blender', 'open')
                    #     play_uncompressed_wave(wf_greeting)
                    #
                    # elif self.Gathered_String == 'open ':
                    #     os.startfile('cmd', 'open')
                    self.empty_count = 0

            else:
                if Command_State == 'Gather':

                    self.empty_count = self.empty_count + 1
                    if self.empty_count >= 3:
                        Command_State = None
                        self.listening = True
                        # variable with 'go' taken out
                        gs = self.Gathered_String[2:]

                        # translate gathered string to french
                        headers = {'content-type': 'plain/text', }

                        r = requests.get(
                            "https://gateway.watsonplatform.net/language-translator/api/v2/translate?model_id=en-fr&text={0}".format(
                                gs), headers=headers, auth=("{username}", "{username}"))

                        print(r.text)

                        # text to speech
                        params = {'content-type': 'audio/wav', 'voice': "fr-FR_ReneeVoice"}

                        response = requests.get(
                            'https://stream.watsonplatform.net/text-to-speech/api/v1/synthesize?accept=audio/wav&text={0}'.format(
                                gs), params=params, auth=('{username}', '{password}'))

                        print(response.content)

                        with open('audio.wav', 'wb') as f:
                            f.write(response.content)

                        audio = wave.open('audio.wav', 'rb')

                        play_uncompressed_wave(audio)

                        # create text file to store text of gathered string and gs (gathered string without 'go')
                        # stt_text = str(self.Gathered_String[2:])
                        f = open('stt.txt', 'w')
                        f.write('English:\n{0}\n'.format(gs))
                        f.write('French:\n{0}'.format(str(r.text)))
                        f.close()
                        self.empty_count = 0


    def stream_audio(self):
        print("Waiting for Watson")
        while not self.listening:
            print('not listening')
            time.sleep(0.1)
        print("Hello Watson")

        p_in = pyaudio.PyAudio()
        stream_in = p_in.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)

        while self.listening:
            for i in range(0, int(RATE / CHUNK * 1)):
                data = stream_in.read(CHUNK, exception_on_overflow=False)
                try:
                    self.send(bytearray(data), binary=True)
                except ssl.SSLError:
                    pass
                except ConnectionAbortedError:
                    pass
            if self.listening:
                try:
                    self.send('{"action": "stop"}')
                except ssl.SSLError:
                    pass
                except ConnectionAbortedError:
                    pass
            time.sleep(0.5)

        stream_in.stop_stream()
        stream_in.close()
        p_in.terminate()
        self.close()

    def close(self, code=1000, reason=''):

        self.listening = False
        WebSocketClient.close(self)


if __name__ == "__main__":

    stt_client = SpeechToTextClient()

    while not stt_client.terminated:
        pass
