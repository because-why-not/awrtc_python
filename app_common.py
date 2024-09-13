#shared helpers between different apps


from abc import abstractmethod
import asyncio
from typing import Dict, Optional, Tuple

from aiortc.contrib.media import MediaPlayer, MediaRecorder
import cv2
import pyaudio

from call_events import CallAcceptedEventArgs, CallEndedEventArgs, CallEventArgs, CallEventType, TrackUpdateEventArgs
from call_peer import CallEventHandler


class TracksProcessor:
    @abstractmethod
    async def on_start(self):
        pass
    @abstractmethod
    async def on_stop(self):
        pass

    @abstractmethod
    def on_track(self, track):
        pass

class LocalPlayback(TracksProcessor):

    def __init__(self, name : str):
        self.name = name
        self.audio_player = pyaudio.PyAudio()
        self.stream = None  # PyAudio stream for audio playback
        self.current_audio_format: Optional[Tuple[int, int, int]] = None

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
                cv2.imshow("Video " + self.name, img)
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
                if self.stream is None or self.current_audio_format != (sample_rate, channels, sample_format):
                    if self.stream:
                        self.stream.stop_stream()
                        self.stream.close()

                    self.stream = self.audio_player.open(
                        format=sample_format,
                        channels=channels,
                        rate=sample_rate,
                        output=True
                    )
                    self.current_audio_format = (sample_rate, channels, sample_format)

                # Write audio data to the stream
                self.stream.write(frame.planes[0].to_bytes())

        asyncio.ensure_future(audio_worker())

# Implementing the interface
class FileStreaming(TracksProcessor):

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


class CallAppEventHandler(CallEventHandler):
    def __init__(self, filename_prefix: Optional[str] = None):
        self.filename_prefix = filename_prefix
        self.connections: Dict[str, TracksProcessor] = {}

    def _get_or_create_processor(self, connection_id: str) -> TracksProcessor:
        if connection_id not in self.connections:
            if self.filename_prefix:
                filename = f"{self.filename_prefix}_{str(connection_id)}.mp4"
                processor = FileStreaming(filename)
            else:
                processor = LocalPlayback(str(connection_id))
            self.connections[connection_id] = processor
        return self.connections[connection_id]

    async def on_call_event(self, args: CallEventArgs):
        if isinstance(args, CallAcceptedEventArgs):
            connection_id = args.connection_id
            processor = self._get_or_create_processor(connection_id)
            await processor.on_start()

        elif isinstance(args, CallEndedEventArgs):
            connection_id = args.connection_id
            if connection_id in self.connections:
                await self.connections[connection_id].on_stop()
                del self.connections[connection_id]

        elif isinstance(args, TrackUpdateEventArgs):
            connection_id = args.connection_id
            processor = self._get_or_create_processor(connection_id)
            processor.on_track(args.track)