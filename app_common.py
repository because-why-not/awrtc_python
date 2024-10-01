from abc import ABC, abstractmethod
import argparse
import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Dict, Optional, Tuple
import signal
import cv2
import pyaudio
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.mediastreams import MediaStreamTrack
from call_events import CallAcceptedEventArgs, CallEndedEventArgs, CallEventArgs, CallEventType, TrackUpdateEventArgs
from call_peer import CallEventHandler
from prefix_logger import PrefixLogger

from aiortc.mediastreams import AudioStreamTrack, VideoStreamTrack, MediaStreamTrack
from dotenv import load_dotenv
from tracks import BeepTrack, MediaSourceNotFoundException, TestVideoStreamTrack


class TracksProcessor(ABC):
    @abstractmethod
    async def on_start(self) -> None:
        pass

    @abstractmethod
    async def on_stop(self) -> None:
        pass

    @abstractmethod
    def on_track(self, track: MediaStreamTrack) -> None:
        pass

class LocalPlayback(TracksProcessor):
    _counter = 0  

    def __init__(self, name: str, logger: PrefixLogger):
        self.logger = logger.get_child("LocalPlayback")
        self._name: str = name
        self._audio_player: pyaudio.PyAudio = pyaudio.PyAudio()
        self._stream: Optional[pyaudio.Stream] = None
        self._current_audio_format: Optional[Tuple[int, int, int]] = None
        self._stop_flag: bool = False
        self._video_task: Optional[asyncio.Task] = None
        self._audio_task: Optional[asyncio.Task] = None

    async def on_start(self) -> None:
        self.logger.info("Starting playback...")
        self._stop_flag = False

    async def on_stop(self) -> None:
        self.logger.info("Stopping playback...")
        self._stop_flag = True
        if self._video_task:
            self._video_task.cancel()
            await asyncio.sleep(0.1)  # Give a short time for the task to cancel
        if self._audio_task:
            self._audio_task.cancel()
            await asyncio.sleep(0.1)  # Give a short time for the task to cancel
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        
        self.logger.info("Playback stopped")

    def on_track(self, track: MediaStreamTrack) -> None:
        self.logger.info(f"Track added: {track.id}")
        if track.kind == "video":
            self.logger.info(f"New video track: {track.id}")
            self._process_video(track)
        elif track.kind == "audio": 
            self.logger.info(f"New audio track: {track.id}")
            self._process_audio(track)

    def _process_video(self, track: MediaStreamTrack) -> None:
        async def video_worker() -> None:
            LocalPlayback._counter += 1
            window_name = "Video " + self._name + "" + str(LocalPlayback._counter)
            try:
                while not self._stop_flag:
                    frame = await track.recv()
                    img = frame.to_ndarray(format="bgr24")
                    cv2.imshow(window_name, img)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                #This does not yet trigger. recv above usually triggers an exception on exit
                self.logger.info("_process_video completed")
            except Exception as e:
                self.logger.error(f"Exception during _process_video: {e}")
            finally:
                cv2.destroyWindow(window_name)
                self.logger.info("_process_video shut down")

        self._video_task = asyncio.ensure_future(video_worker())

    def _process_audio(self, track: MediaStreamTrack) -> None:
        async def audio_worker() -> None:
            try:
                while not self._stop_flag:
                    frame = await track.recv()
                    sample_rate: int = frame.sample_rate
                    channels: int = len(frame.layout.channels)
                    sample_format: int = pyaudio.paInt16

                    if self._stream is None or self._current_audio_format != (sample_rate, channels, sample_format):
                        if self._stream:
                            self._stream.stop_stream()
                            self._stream.close()

                        self._stream = self._audio_player.open(
                            format=sample_format,
                            channels=channels,
                            rate=sample_rate,
                            output=True
                        )
                        self._current_audio_format = (sample_rate, channels, sample_format)

                    self._stream.write(frame.planes[0].to_bytes())
                #This does not yet trigger. recv above usually triggers an exception on exit
                self.logger.info("_process_audio completed")
            except Exception as e:
                self.logger.error(f"Exception during _process_audio: {e}")
            finally:
                self.logger.info("_process_audio shut down")

        self._audio_task = asyncio.ensure_future(audio_worker())

class FileStreaming(TracksProcessor):

    def __init__(self, filename: str, logger: PrefixLogger):
        self.logger = logger.get_child("FileStreaming")
        self._recorder: MediaRecorder = MediaRecorder(filename, None, None)

    async def on_start(self) -> None:
        self.logger.info("Starting recording ...")
        await self._recorder.start()

    async def on_stop(self) -> None:
        self.logger.info("Stopping recording")
        await self._recorder.stop()
        self.logger.info("Recording stopped")

    def on_track(self, track: MediaStreamTrack) -> None:
        self.logger.info(f"Add track: {track.id}")
        self._recorder.addTrack(track)


def setup_app_logger(): 
    logger = PrefixLogger("app")
    logger.info("app logger started")
    return logger


class CallAppEventHandler(CallEventHandler):
    def __init__(self, filename_prefix: Optional[str] = None):
        self.logger = setup_app_logger()
        self._filename_prefix: Optional[str] = filename_prefix
        self._connections: Dict[str, TracksProcessor] = {}

    def _get_or_create_processor(self, connection_id: str) -> TracksProcessor:
        if connection_id not in self._connections:
            processor: TracksProcessor 
            if self._filename_prefix:
                filename = f"{self._filename_prefix}_{str(connection_id)}.mp4"
                processor = FileStreaming(filename, self.logger)
            else:
                processor = LocalPlayback(str(connection_id), self.logger)
            self._connections[connection_id] = processor
        return self._connections[connection_id]

    async def on_call_event(self, args: CallEventArgs) -> None:
        if isinstance(args, CallAcceptedEventArgs):
            connection_id: str = args.connection_id
            processor: TracksProcessor = self._get_or_create_processor(connection_id)
            self.logger.info(f"Call accepted for connection {connection_id}")
            await processor.on_start()

        elif isinstance(args, CallEndedEventArgs):
            connection_id: str = args.connection_id
            if connection_id in self._connections:
                self.logger.info(f"Call ended for connection {connection_id}")
                await self._connections[connection_id].on_stop()
                del self._connections[connection_id]

        elif isinstance(args, TrackUpdateEventArgs):
            connection_id: str = args.connection_id
            processor: TracksProcessor = self._get_or_create_processor(connection_id)
            self.logger.info(f"Track update for connection {connection_id}")
            processor.on_track(args.track)



#called at the start of example apps to allow cleanup
#when the user presses ctrl+c. 
def setup_signal_handling(task: asyncio.Task):
    def _signal_handler(sig, frame):
        print(f"Received signal {sig}. Cancel task")
        task.cancel()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)




def parse_args():
    load_dotenv()
    default_address = os.getenv('ADDRESS', "abc123")
    parser = argparse.ArgumentParser(description="Run the call example application.")

    parser.add_argument('address', nargs='?', default=default_address, 
                        help='Specify the address / passphrase (default: %(default)s)')
    parser.add_argument('-l', '--listen', action='store_true', help='Set to listen mode')
    parser.add_argument('--audio', nargs='?', const='dummy', default=None, 
                        help='Specify audio device. For now only "dummy" is supported or no value for default.')
    parser.add_argument('--video', nargs='?', const='dummy', default=None,
                            help='Specify video device name. For now only "dummy" is supported or no value for default.')
    parser.add_argument('--from-file', metavar='PATH', 
                        help='Specify a file to send audio and video from. A path must be provided.')
    parser.add_argument('--to-file', metavar='PATH', 
                        help='Specify a file to store video at')
    
            
    args = parser.parse_args()
    
    print("Set flags:")
    for arg, value in vars(args).items():
        if value is not None and value is not False:
            print(f"  {arg}: {value}")
    return args

def get_video_track(video_arg: str | None) -> VideoStreamTrack | None:
    if video_arg is None:
        return None
    elif video_arg.lower() in ["dummy"]:
        #using the dummy video device as default for now
        return TestVideoStreamTrack()
    else:
        raise MediaSourceNotFoundException(f"Unknown video source: {video_arg}")

def get_audio_track(audio_arg: str | None) -> AudioStreamTrack | None:
    if audio_arg is None:
        return None
    elif audio_arg.lower() in ["dummy"]:
        #using the dummy video device as default for now
        return BeepTrack()
    else:
        raise MediaSourceNotFoundException(f"Unknown video source: {audio_arg}")


@dataclass
class MediaTracks:
    video: MediaStreamTrack | None
    audio: MediaStreamTrack | None

    def __iter__(self):
        return iter((self.video, self.audio))

def get_tracks_from_file(path: str | None, to: MediaTracks):
    if path is None:
        return MediaTracks(video=None, audio=None)
    player = MediaPlayer(path, loop=True)
    to.video = player.video
    to.audio = player.audio
    return 

#This gets tracks based on the arguments used
def get_tracks_from_args(args) -> MediaTracks:
    tracks = MediaTracks(video=None, audio=None)

    #try get tracks from the file first
    get_tracks_from_file(args.from_file, tracks)

    #tracks from the --video and --audio flags
    if tracks.video is None:
        tracks.video = get_video_track(args.video)

    if tracks.audio is None:
        tracks.audio = get_audio_track(args.audio)
    return tracks
