import asyncio
import os
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from dotenv import load_dotenv
import cv2
import numpy as np
import pyaudio
from aiortc import VideoStreamTrack
from aiortc.mediastreams import AudioStreamTrack
from call import Call
from call_peer import TracksObserver
from test_tracks import BeepTrack, TestVideoStreamTrack

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)

# Implementing the interface
class FileStreamingHandler(TracksObserver):

    def __init__(self, filename):
        self.recorder = MediaRecorder(filename)

    async def on_start(self):
        print("Starting recording ...")
        await self.recorder.start()

    async def on_stop(self):
        print("Stopping recording")
        await self.recorder.stop()
        print("Recording stopped")

    def on_track(self, track):
        print(f"add track: {track.id}")
        self.recorder.addTrack(track)


class LocalPlayackHandler(TracksObserver):

    def __init__(self): #keep filename to match the api for now
        self.recorder = None  # Optionally still record to file
        self.audio_player = pyaudio.PyAudio()
        self.stream = None  # PyAudio stream for audio playback

    async def on_start(self):
        print("Starting playback...")

    async def on_stop(self):
        print("Stopping playback...")
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

    def on_track(self, track):
        print(f"Track added: {track.id}")

        if track.kind == "video":
            print(f"new video track: {track.id}")
            self.process_video(track)
        elif track.kind == "audio": 
            print(f"new audio track: {track.id}")
            self.process_audio(track)

    def process_video(self, track):
        # This function processes video frames and displays them
        async def video_worker():
            while True:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")  # Convert video frame to a NumPy array
                cv2.imshow("Video", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            cv2.destroyAllWindows()

        asyncio.ensure_future(video_worker())

    def process_audio(self, track):
        async def audio_worker():
            while True:
                # Receive the next audio frame
                frame = await track.recv()

                # Extract audio format info dynamically from the frame
                sample_rate = frame.sample_rate  # Usually 48000 Hz
                channels = len(frame.layout.channels)
                sample_format = pyaudio.paInt16  # Assuming 16-bit PCM, may need adjustments

                # If the format changes, restart the audio stream
                if self.stream is None or self.current_format != (sample_rate, channels, sample_format):
                    if self.stream:
                        self.stream.stop_stream()
                        self.stream.close()

                    self.stream = self.audio_player.open(
                        format=sample_format,
                        channels=channels,
                        rate=sample_rate,
                        output=True
                    )
                    self.current_format = (sample_rate, channels, sample_format)

                # Write audio data to the stream
                self.stream.write(frame.planes[0].to_bytes())

        asyncio.ensure_future(audio_worker())

def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")
    # True - Read from a video file and write to a video file
    # False - Send dummy data tracks and playback via OpenCV and local speakers
    video_file = False
    sending = "video.mp4"
    receiving = "inc.mp4"
    if video_file:
        track_handler = FileStreamingHandler(receiving)
    else:
        track_handler = LocalPlayackHandler()
    call  = Call(uri, track_handler)

    if video_file:
        player = MediaPlayer(sending, loop=True)
        call.attach_track(player.video)
        call.attach_track(player.audio)
    else:
        call.attach_track(TestVideoStreamTrack())
        call.attach_track(BeepTrack())
        
        



    loop = asyncio.get_event_loop()
    
    try:
        #loop.run_until_complete(call.listen(address))
        loop.run_until_complete(call.call(address))
    except KeyboardInterrupt:
        pass
    finally:        
        print("Shutting down...")
        loop.run_until_complete(call.dispose())
        print("shutdown complete.")

if __name__ == "__main__":
    print("Start")
    main()
    