import asyncio
import colorsys
from dataclasses import dataclass
import fractions
from aiortc.contrib.media import MediaRecorderContext
import cv2
import numpy as np
import time
import av
from av import VideoFrame
from aiortc import VideoStreamTrack
from aiortc.mediastreams import VIDEO_TIME_BASE, AudioStreamTrack, MediaStreamError, MediaStreamTrack
from av import AudioFrame
import logging
logger = logging.getLogger(__name__)

#Note these tracks are just used for quick testing via claude. They might be buggy

class BaseVideoStreamTrack(VideoStreamTrack):
    def __init__(self, fps=30):
        super().__init__()
        self.fps = fps
        self.frame_time = 1 / self.fps
        self.time_base = fractions.Fraction(1, 90000)  # Use 90kHz timebase
        self.start_time = time.time()
        self.last_frame_time = self.start_time
        self.counter = 0

    async def recv(self):
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        
        if elapsed < self.frame_time:
            await asyncio.sleep(self.frame_time - elapsed)
            current_time = time.time()
        
        pts = int((current_time - self.start_time) * 90000)

        frame = await self.create_frame(pts)
        frame.pts = pts
        frame.time_base = self.time_base

        #print(f"Frame {self.counter}: Time since last frame: {current_time - self.last_frame_time:.6f}, PTS: {pts}")
        
        self.last_frame_time = current_time
        self.counter += 1
        return frame

    async def create_frame(self, pts):
        """
        Override this method in subclasses to create the actual frame content.
        """
        raise NotImplementedError("Subclasses must implement create_frame method")


class ColorVideoStreamTrack(BaseVideoStreamTrack):
    def __init__(self, fps=30):
        super().__init__(fps)

    async def create_frame(self, pts):
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        h = (self.counter % 90) / 90.0  # Cycle hue every 3 seconds (90 frames at 30fps)
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        img[:, :, 0] = int(r * 255)
        img[:, :, 1] = int(g * 255)
        img[:, :, 2] = int(b * 255)

        return VideoFrame.from_ndarray(img, format="rgb24")
    
class TestVideoStreamTrack(BaseVideoStreamTrack):
    def __init__(self, fps=30, width=640, height=480):
        super().__init__(fps)
        self.width = width
        self.height = height
        self.box_size = min(width, height) // 5
        
        # Initialize positions for red, green, and blue boxes
        self.red_pos = [0, 0]  # Moves diagonally
        self.green_pos = [0, height // 2]  # Moves horizontally
        self.blue_pos = [width // 2, 0]  # Moves vertically

    async def create_frame(self, pts):
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Update positions
        self.red_pos[0] = (self.red_pos[0] + 2) % self.width
        self.red_pos[1] = (self.red_pos[1] + 2) % self.height
        
        self.green_pos[0] = (self.green_pos[0] + 3) % self.width
        
        self.blue_pos[1] = (self.blue_pos[1] + 3) % self.height
        
        # Draw boxes
        self.draw_box(img, self.red_pos, [255, 0, 0])  # Red box
        self.draw_box(img, self.green_pos, [0, 255, 0])  # Green box
        self.draw_box(img, self.blue_pos, [0, 0, 255])  # Blue box
        
        
        # Add frame counter as text
        #self.draw_text(img, f"Frame: {self.counter}")
        
        
        return VideoFrame.from_ndarray(img, format="rgb24")

    def draw_box(self, img, pos, color):
        x, y = pos
        img[y:y+self.box_size, x:x+self.box_size] = color

    def draw_text(self, img, text):
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, text, (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)

AUDIO_PTIME = 0.02



class BeepTrack(AudioStreamTrack):
    def __init__(self, frequency=440, sample_rate=48000, beep_duration=0.1, interval=1.0):
        super().__init__()
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.samples_per_frame = int(self.sample_rate * AUDIO_PTIME)
        self.beep_duration = beep_duration
        self.interval = interval
        self.beep_samples = int(self.beep_duration * self.sample_rate)
        self.interval_samples = int(self.interval * self.sample_rate)
        
        # Pre-generate the beep
        self.beep = self._generate_beep()
        
        self.sample_index = 0

    def _generate_beep(self):
        t = np.linspace(0, self.beep_duration, self.beep_samples, False)
        beep = np.sin(2 * np.pi * self.frequency * t)
        
        # Apply envelope
        envelope = np.ones_like(beep)
        attack_samples = int(0.01 * self.sample_rate)  # 10ms attack
        decay_samples = int(0.01 * self.sample_rate)   # 10ms decay
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
        envelope[-decay_samples:] = np.linspace(1, 0, decay_samples)
        beep *= envelope
        
        return beep

    async def recv(self):
        if not hasattr(self, "_timestamp"):
            self._start = time.time()
            self._timestamp = 0
        else:
            self._timestamp += self.samples_per_frame
            wait = self._start + (self._timestamp / self.sample_rate) - time.time()
            await asyncio.sleep(max(0, wait))

        # Generate audio
        start_sample = self.sample_index % self.interval_samples
        end_sample = start_sample + self.samples_per_frame
        
        if start_sample < self.beep_samples:
            # We're in a beep
            beep_portion = self.beep[start_sample:min(end_sample, self.beep_samples)]
            audio = np.zeros(self.samples_per_frame)
            audio[:len(beep_portion)] = beep_portion
        else:
            # We're in silence
            audio = np.zeros(self.samples_per_frame)

        # Convert to 16-bit PCM
        audio = (audio * 32767).astype(np.int16)

        frame = AudioFrame(format="s16", layout="mono", samples=self.samples_per_frame)
        frame.planes[0].update(audio.tobytes())
        frame.pts = self._timestamp
        frame.sample_rate = self.sample_rate
        frame.time_base = fractions.Fraction(1, self.sample_rate)

        self.sample_index += self.samples_per_frame

        return frame

    def change_frequency(self, new_frequency):
        """Allow dynamic change of frequency for testing"""
        self.frequency = new_frequency
        self.beep = self._generate_beep()  # Regenerate the beep with the new frequency
        logger.info(f"Changed frequency to {new_frequency} Hz")

class SineWaveTrack(AudioStreamTrack):
    def __init__(self, frequency=800, sample_rate=48000):
        super().__init__()
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.samples_per_frame = int(self.sample_rate * AUDIO_PTIME)
        self.sample_index = 0

    async def recv(self):
        if not hasattr(self, "_timestamp"):
            self._start = time.time()
            self._timestamp = 0
        else:
            self._timestamp += self.samples_per_frame
            wait = self._start + (self._timestamp / self.sample_rate) - time.time()
            await asyncio.sleep(wait)

        # Generate sine wave
        t = np.arange(self.sample_index, self.sample_index + self.samples_per_frame) / self.sample_rate
        audio = np.sin(2 * np.pi * self.frequency * t)

        # Convert to 16-bit PCM
        audio = (audio * 32767).astype(np.int16)

        frame = AudioFrame(format="s16", layout="mono", samples=self.samples_per_frame)
        frame.planes[0].update(audio.tobytes())
        frame.pts = self._timestamp
        frame.sample_rate = self.sample_rate
        frame.time_base = fractions.Fraction(1, self.sample_rate)

        self.sample_index += self.samples_per_frame

        return frame

    def change_frequency(self, new_frequency):
        """Allow dynamic change of frequency for testing"""
        self.frequency = new_frequency
        logger.info(f"Changed frequency to {new_frequency} Hz")

class MediaSourceNotFoundException(Exception):
    """Exception raised when a media source is not found."""
    
    def __init__(self, source, message="Media source not found"):
        self.source = source
        self.message = f"{message}: {source}"
        super().__init__(self.message)





class CustomMediaRecorderContext:
    def __init__(self, stream) -> None:
        self.started = False
        self.stream = stream
        self.task : asyncio.Task[None] | None= None
@dataclass
class RecorderConfig:
    #recording width. If not defaults to the width of the first frame
    width:int| None = None
    #recording height. If not defaults to the height of the first frame
    height:int| None = None
    #rate set when calling add_stream.
    #This is suppose to be the frame rate of the incoming video but
    #WebRTC can change on the fly. Depending on codecs used this might lead to errors
    #but most should support variable framerates no matter what is set here
    rate: int = 60
    video_bit_rate:int| None = None
    #webm file is written this can be used to set vp8 or vp9
    video_stream_codec:str| None = None
    container_format: str | None = None
    container_options = None


class CustomMediaRecorder:
    """
    Directly based on MediaRecorder from
    https://github.com/aiortc/aiortc/blob/main/src/aiortc/contrib/media.py
    Added VP8 support (picked when webm is used as suffix)

    """

    def __init__(self, file, config: RecorderConfig = RecorderConfig()):
        self.__container = av.open(file=file, format=config.container_format, mode="w", options=config.container_options)
        self.__tracks : dict[MediaStreamTrack, CustomMediaRecorderContext]= {}
        self._config = config
        #used to check the frame timing
        self.VERBOSE = False
        self._last_video_frame = 0
        self._last_video_package = 0
        

    def addTrack(self, track: MediaStreamTrack) -> None:
        """
        Add a track to be recorded.

        :param track: A :class:`aiortc.MediaStreamTrack`.
        """
        if track.kind == "audio":
            if self.__container.format.name in ("wav", "alsa", "pulse"):
                codec_name = "pcm_s16le"
            elif self.__container.format.name == "mp3":
                codec_name = "mp3"     
            if self.__container.format.name in ("webm"):
                codec_name = "libopus"
            else:
                codec_name = "aac"
            stream = self.__container.add_stream(codec_name)
        else:

            if self.__container.format.name == "image2":
                stream = self.__container.add_stream("png", rate=self._config.rate)
                stream.pix_fmt = "rgb24"
            elif self.__container.format.name == "webm":
                codec = "vp8" if self._config.video_stream_codec is None else self._config.video_stream_codec
                stream = self.__container.add_stream(codec)
                stream.pix_fmt = "yuv420p"
            else:
                stream = self.__container.add_stream("libx264", rate=self._config.rate)
                stream.pix_fmt = "yuv420p"
            # Allows incoming FPS higher than the rate set above
            # Fix for error "non-strictly-monotonic PTS error"
            stream.time_base = VIDEO_TIME_BASE
        self.__tracks[track] = CustomMediaRecorderContext(stream)
        

    async def start(self) -> None:
        """
        Start recording.
        """
        for track, context in self.__tracks.items():
            if context.task is None:
                context.task = asyncio.ensure_future(self.__run_track(track, context))

    async def stop(self) -> None:
        """
        Stop recording.
        """
        if self.__container:
            for track, context in self.__tracks.items():
                if context.task is not None:
                    context.task.cancel()
                    context.task = None
                    for packet in context.stream.encode(None):
                        self.__container.mux(packet)
            self.__tracks = {}

            if self.__container:
                self.__container.close()
                self.__container = None

    async def __run_track(
        self, track: MediaStreamTrack, context: CustomMediaRecorderContext ) -> None:
        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                return

            if not context.started:
                # set width/height and bitrate if available
                if isinstance(frame, VideoFrame):
                    context.stream.width = self._config.width if self._config.width is not None else frame.width
                    context.stream.height = self._config.height if self._config.height is not None else frame.height
                    if self._config.video_bit_rate is not None:
                        context.stream.bit_rate = self._config.video_bit_rate 
                context.started = True
            
            if isinstance(frame, VideoFrame):
                diff = frame.pts - self._last_video_frame
                self._last_video_frame = frame.pts
                if self.VERBOSE:
                    logger.info(f"MediaRecorder video frame pts {frame.pts} diff {diff}")

            for packet in context.stream.encode(frame):
                if isinstance(frame, VideoFrame):
                    if self.VERBOSE:
                        logger.info(f"MediaRecorder video packet dts {packet.dts}")
                    #for libx264 drop packages that have the same dts. This happens when we receive 
                    #too many frames / frames with pts too close together
                    if self._last_video_package > 0 and self._last_video_package == packet.dts and context.stream.name == "libx264":
                        #fallback to prevent crash of libx264
                        logger.warning(f"MediaRecorder will drop duplicate package with dts {packet.dts}. " 
                                       + " This can happen if libx264 receives more frames than the set framerate or the timestamp is too close together")
                        continue
                    self._last_video_package = packet.dts
                    
                self.__container.mux(packet)
    
    @staticmethod
    def get_default_config():
        config = RecorderConfig()
        config.video_bit_rate = 2_500_000
        config.width = 1280
        config.height = 720
        config.rate = 60
        return config