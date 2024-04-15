import asyncio
import os
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from dotenv import load_dotenv

from call import Call
from call_peer import TracksObserver

load_dotenv()


# Implementing the interface
class MyTracksHandler(TracksObserver):

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
    
def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")

    call  = Call(uri, MyTracksHandler("inc.mp4"))
    sending = "video.mp4"
    player = MediaPlayer(sending, loop=True)
    call.attach_track(player.video)
    call.attach_track(player.audio)



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
    