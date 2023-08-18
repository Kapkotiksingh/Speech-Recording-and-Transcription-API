from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import pyaudio
import wave
import threading
import time
import nltk
import speech_recognition as sr
import textrank

nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')
nltk.download('wordnet')

class RecordingThread(threading.Thread):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.p = pyaudio.PyAudio()
        self.frames = []
        self.stopped = threading.Event()
        self.recording = threading.Event()
        self.start_time = None

    def set_recording_duration(self, duration):
        self.recording_duration = duration

    def run(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100

        self.start_time = time.time()

        stream = self.p.open(format=FORMAT,
                             channels=CHANNELS,
                             rate=RATE,
                             input=True,
                             frames_per_buffer=CHUNK)

        while not self.stopped.is_set() and self.recording.is_set():
            data = stream.read(CHUNK)
            self.frames.append(data)

        stream.stop_stream()
        stream.close()
        self.p.terminate()

        wf = wave.open(self.filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        r = sr.Recognizer()
        with sr.AudioFile(self.filename) as source:
            audio_text = r.record(source)

        try:
            transcribed_text = r.recognize_google(audio_text, language="en-US")
            transcribed_text = nltk.word_tokenize(transcribed_text)

            text_filename = self.filename.replace(".wav", "_transcribed.txt")
            with open(text_filename, 'w') as file:
                file.write(" ".join(transcribed_text))
            print("Transcription saved to:", text_filename)

            summarized_text = textrank.summarize(transcribed_text, ratio=0.2)
            summarized_filename = self.filename.replace(".wav", "_summarized.txt")
            with open(summarized_filename, 'w') as file:
                file.write(summarized_text)
            print("Summarized text saved to:", summarized_filename)

        except sr.UnknownValueError:
            print("Speech recognition could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")


    def stop(self):
        self.stopped.set()
        self.recording.clear()
        self.end_time = time.time()
        self.recording_duration = self.end_time - self.start_time

class RecordingThreadManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.recording_thread = None
        return cls._instance

    def create_recording_thread(self, filename):
        if self.recording_thread is None or not self.recording_thread.is_alive():
            self.recording_thread = RecordingThread(filename)
            self.recording_thread.set_recording_duration(None)
            self.recording_thread.recording.set()
            self.recording_thread.start()

    def stop_recording_thread(self):
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.stop()
            self.recording_thread.join()
            recording_duration = (
                self.recording_thread.recording_duration
                if hasattr(self.recording_thread, "recording_duration")
                else None
            )
            self.recording_thread = None
            return recording_duration
        return None

class RecordingApiView(APIView):
    def post(self, request, format=None):
        if request.data.get('action') == 'start':
            audio_filename = "output.wav"
            recording_thread_manager = RecordingThreadManager()
            recording_thread_manager.create_recording_thread(audio_filename)
            return Response({"message": "Recording started."}, status=status.HTTP_200_OK)
        elif request.data.get('action') == 'stop':
            recording_thread_manager = RecordingThreadManager()
            recording_duration = recording_thread_manager.stop_recording_thread()
            if recording_duration is not None:
                return Response(
                    {"message": "Recording stopped.", "recording_duration": recording_duration},
                    status=status.HTTP_200_OK,
                )
            return Response({"message": "No active recording thread."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"message": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, format=None):
        data_folder = "data/"
        text_filename = data_folder + "output_transcribed.txt"
        summarized_filename = data_folder + "output_summarized.txt"

        try:
            with open(text_filename, 'r') as file:
                transcribed_text = file.read()
            with open(summarized_filename, 'r') as file:
                summarized_text = file.read()
        except FileNotFoundError:
            return Response({"message": "Text data not available yet."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "transcribed_text": transcribed_text,
            "summarized_text": summarized_text
        }, status=status.HTTP_200_OK)