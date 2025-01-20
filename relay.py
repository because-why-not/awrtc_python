'''
Test scenario:
1. Call python relay.py. This will automatically listen on the address "usera" and "userb"
2. Open the call app in the Unity Editor or in the browser:
https://because-why-not.com/files/webrtcsamples/v1.0.4/awrtc_browser/callapp.html
3. Tick video and audio in the app and enter "usera" and press join
Wait until the app connects to the server. You should see log looking like this:
INFO:relayapp.relay_usera:Call accepted for connection ConnectionId(16384)
INFO:relayapp.relay_usera.RelayTracksProcessor:Starting recording ...

4. In another instance of call app untick audio and video, enter "userb" and then press join
You should see another message: 
INFO:relayapp.relay_userb:Call accepted for connection ConnectionId(16384)
(Note: The server will attempt to record audio/video from the 2nd app but it can not yet relay it)

5. The first call app should now be streaming audio and video to the second. The server is relaying this media
data and recording at the same time. 

6. Exit the server by pressing ctrl + C

Known issues so far:
* Framerate and quality will be worse 
* Error still happens randomly which will stop the video feed:
[libx264 @ 0000029baceaa140] non-strictly-monotonic PTS
[mp4 @ 0000029baa72e900] Application provided invalid, non monotonically increasing dts to muxer in stream 1: 245760 >= 245760
* Relay only works in one direction

'''
import asyncio
import os
from aiortc.mediastreams import MediaStreamTrack
from dotenv import load_dotenv

from app_common import TracksProcessor
from call import Call
from call_events import CallAcceptedEventArgs, CallEndedEventArgs, CallEventArgs, TrackUpdateEventArgs
from call_peer import CallEventHandler
from prefix_logger import PrefixLogger
from tracks import CustomMediaRecorder

load_dotenv()
import logging
logging.basicConfig(level=logging.INFO)

uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
gLogger = PrefixLogger("relayapp")
gLogger.info("app logger started")

class RelayTracksProcessor(TracksProcessor):

    def __init__(self, filename: str, logger: PrefixLogger):
        self.logger = logger.get_child("RelayTracksProcessor")
        config = CustomMediaRecorder.get_default_config()
        self._recorder: CustomMediaRecorder = CustomMediaRecorder(filename, config)

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


#First prototype for a relay server.
#It will create two calls and wait on address "usera" and "userb"
#then connect the two users to each other while recording their feeds. 
#NOTE: THIS DOES NOT YET WORK PROPERLY!
#The user that connects first will not receive the feed from the user that connects second
#because the tracks aren't attached correctly to an already active connection yet
#This will be fixed later.
#Recording of both tracks and receiving for the 2nd user should work.
class RelayCall(CallEventHandler):
    processor: RelayTracksProcessor
    call: Call
    address: str
    inc_video_track: MediaStreamTrack | None
    inc_audio_track: MediaStreamTrack | None

    other: 'RelayCall'

    logger: PrefixLogger

    def __init__(self, address):
        self.address = address
        self.logger = gLogger.get_child("relay_" + address)
        self.processor = RelayTracksProcessor(address + ".mp4", self.logger)
        self.inc_video_track = None
        self.inc_audio_track = None
        self.call = Call(uri, self, False)
    
    def setOther(self, other: 'RelayCall'):
        self.other = other
    
    async def dispose(self):
        await self.call.dispose()

    async def listen(self):
        self.logger.info("listening ...")
        await self.call.listen(self.address)
    
    async def on_start(self):
        await self.processor.on_start()
        self.other.attach(self.inc_video_track, self.inc_audio_track)
    
    def attach(self, video_track: MediaStreamTrack | None, audio_track: MediaStreamTrack | None):
        if video_track is not None:
            self.call.attach_track(video_track)
        if audio_track is not None:
            self.call.attach_track(audio_track)
        

    async def on_end(self):
        await self.processor.on_stop()

    async def on_call_event(self, args: CallEventArgs) -> None:
        if isinstance(args, CallAcceptedEventArgs):
            connection_id = args.connection_id
            self.logger.info(f"Call accepted for connection {connection_id}")
            await self.on_start()

        elif isinstance(args, CallEndedEventArgs):
            connection_id = args.connection_id
            self.logger.info(f"Call ended for connection {connection_id}")
            await self.on_end()

        elif isinstance(args, TrackUpdateEventArgs):
            connection_id = args.connection_id
            self.logger.info(f"Track update for connection {connection_id}")
            self.processor.on_track(args.track)
            if args.track.kind == "video":
                self.inc_video_track = args.track
                self.logger.info(f"video track ready for relay from " + self.address)
            else:
                self.inc_audio_track = args.track
                self.logger.info(f"audio track ready for relay from " + self.address)

    

async def main():

    load_dotenv()
    call_usera  = RelayCall("usera")
    call_userb  = RelayCall("userb")
    call_usera.setOther(call_userb)
    call_userb.setOther(call_usera)
    
    
    try:
            loop_usera =  asyncio.create_task(call_usera.listen())
            loop_userb =  asyncio.create_task(call_userb.listen())
            await asyncio.gather(loop_usera, loop_userb)
            
            print("loops ended")
    except asyncio.CancelledError:
        #This should trigger when our exit signal (e.g. ctrl+c) is triggered
        print("CancelledError triggered. Starting controlled shutdown")
    finally:
        print("Shutting down...")
        await call_usera.dispose()
        await call_userb.dispose()
        print("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
    