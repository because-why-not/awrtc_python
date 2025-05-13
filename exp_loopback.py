import asyncio
import os
from aiortc.mediastreams import AudioStreamTrack, VideoStreamTrack
from dotenv import load_dotenv
from app_common import CallAppEventHandler, setup_signal_handling
from call import Call
import logging
from call_events import CallAcceptedEventArgs, CallEventArgs, DataMessageEventArgs, MessageEventArgs
from tracks import BeepTrack, TestVideoStreamTrack
from websocket_network import ConnectionId

'''
Quick and dirt loopback test for sending & receiving data channel messages. 
It will automatically send and receive messages every 5 seconds. 

Address is hardcoded to "pyloop" below

Optionally:
* Attach a video track to the call (uncommend tracks below)
* Attach an audio track to the call (uncommend tracks below)
* start only the listener or caller task to run them as separate processes
'''



logging.basicConfig(level=logging.INFO)

address = "pyloop"

call_listen : Call | None = None
call_outgoing : Call | None = None


class LoopbackCallAppEventHandler(CallAppEventHandler):
    
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.call : Call | None = None
        self.task: asyncio.Task | None = None

    def set_call(self, call: Call):
        self.call = call

    async def on_call_event(self, args: CallEventArgs) -> None:
        # Call the base class behavior
        await super().on_call_event(args)
        if isinstance(args, CallAcceptedEventArgs):
            if self.call:
                self.task = asyncio.create_task(self._send_messages_loop(self.call, args.connection_id))

    async def _send_messages_loop(self, call: Call, connection_id: ConnectionId):
        try:
            while True:
                await asyncio.sleep(5)
                await call.send(f"hello from {self.name} unreliable set to True", True, connection_id)
                await asyncio.sleep(5)
                await call.send(f"hello from {self.name} unreliable set to False", False, connection_id)
        except asyncio.CancelledError:
            pass  # Gracefully exit on cancellation

async def loop_listener():
    global call_listen
    video_track : VideoStreamTrack | None = None
    audio_track : AudioStreamTrack  | None = None

    #uncomment to test media tracks
    #video_track = TestVideoStreamTrack()
    #audio_track = BeepTrack()

    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    track_handler = LoopbackCallAppEventHandler("listener")
    call_listen  = Call(uri, track_handler)
    track_handler.set_call(call_listen)
    if video_track:
        call_listen.attach_track(video_track)
    
    if audio_track:
        call_listen.attach_track(audio_track)
    
    await call_listen.listen(address)

async def loop_caller():
    global call_outgoing
    video_track : VideoStreamTrack | None = None
    audio_track : AudioStreamTrack  | None = None

    #uncomment to test media tracks
    #video_track = TestVideoStreamTrack()
    #audio_track = BeepTrack()

    await asyncio.sleep(0.5)

    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    track_handler = LoopbackCallAppEventHandler("caller")
    call_outgoing  = Call(uri, track_handler)
    track_handler.set_call(call_outgoing)
    if video_track:
        call_outgoing.attach_track(video_track)
    
    if audio_track:
        call_outgoing.attach_track(audio_track)

    await call_outgoing.call(address)

async def loop():
    await asyncio.gather(loop_listener(), loop_caller())
    #comment above and uncommend below to test only a single task per process
    #await loop_listener()
    #await loop_caller()

async def main():
    
    global call_listen
    global call_outgoing

    load_dotenv()
    try:
        
        main_loop =  asyncio.create_task(loop())
        setup_signal_handling(main_loop)
        await main_loop
        
        print("ended")
    except asyncio.CancelledError:
        #This should trigger when our exit signal (e.g. ctrl+c) is triggered
        print("CancelledError triggered. Starting controlled shutdown")
    finally:
        print("Shutting down...")
        if call_listen: 
            print("Disposing call_listen")
            await call_listen.dispose()
        if call_outgoing: 
            print("call_outgoing")
            await call_outgoing.dispose()
        print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
    