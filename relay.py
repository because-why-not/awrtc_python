import asyncio
import os
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.mediastreams import MediaStreamTrack
from dotenv import load_dotenv

from app_common import TracksProcessor
from call import Call
from call_events import CallAcceptedEventArgs, CallEndedEventArgs, CallEventArgs, TrackUpdateEventArgs
from call_peer import CallEventHandler
from prefix_logger import PrefixLogger

load_dotenv()
import logging
logging.basicConfig(level=logging.INFO)

uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
gLogger = PrefixLogger("relayapp")
gLogger.info("app logger started")


class RelayTracksProcessor(TracksProcessor):

    def __init__(self, filename: str, logger: PrefixLogger):
        self.logger = logger.get_child("RelayTracksProcessor")
        self._recorder: MediaRecorder = MediaRecorder(filename)

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
    inc_video_track: MediaStreamTrack
    inc_audio_track: MediaStreamTrack

    other: 'RelayCall'

    logger: PrefixLogger

    def __init__(self, address):
        self.address = address
        self.logger = gLogger.get_child("relay_" + address)
        self.processor = RelayTracksProcessor(address + ".mp4", self.logger)
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
        await self.other.attach(self.inc_video_track, self.inc_audio_track)
    
    async def attach(self, video_track: MediaStreamTrack, audio_track: MediaStreamTrack):
        self.call.attach_track(video_track)
        self.call.attach_track(audio_track)
        

    async def on_end(self):
        await self.processor.on_end()

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
        await loop_usera.dispose()
        await loop_userb.dispose()
        print("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
    