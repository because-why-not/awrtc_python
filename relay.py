import asyncio
import os
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from dotenv import load_dotenv

from call import Call
from call_peer import CallEventHandler

load_dotenv()


uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')


# Implementing the interface
class RelayTracks(CallEventHandler):

    

    def __init__(self, address):
        self.address = address
        self.vtrack = None
        self.atrack = None

    async def relay(self):
        self.call  = Call(uri)
        if self.vtrack:
            self.call.attach_track(self.vtrack)
        if self.atrack:
            self.call.attach_track(self.atrack)
        print("Listening now ....")
        await self.call.listen(self.address)


    async def on_start(self):
        print("Starting relay ...")
        asyncio.create_task(self.relay())
        

    async def on_stop(self):
        print("Stopping relay")
        await self.call.dispose()
        

    def on_track(self, track):
        print(f"add track: {track.id}")
        if track.kind == "video":
            self.vtrack = track
        else:
            self.atrack = track

    

    
def main():

    call  = Call(uri, RelayTracks("relay123"))



    loop = asyncio.get_event_loop()
    
    try:
        #loop.run_until_complete(call.listen(address))
        loop.run_until_complete(call.listen("passphrase123"))
    except KeyboardInterrupt:
        pass
    finally:        
        print("Shutting down...")
        loop.run_until_complete(call.dispose())
        print("shutdown complete.")

if __name__ == "__main__":
    print("Start")
    main()
    