import asyncio
import os
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from dotenv import load_dotenv

from call import Call

load_dotenv()

def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")

    call  = Call(uri)
    sending = "video.mp4"
    player = MediaPlayer(sending)
    call.attach_track(player.video)
    call.attach_track(player.audio)

    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(call.listen(address))
        #loop.run_until_complete(call.call(address))
    except KeyboardInterrupt:
        pass
    finally:        
        print("Shutting down...")
        loop.run_until_complete(call.dispose())
        print("shutdown complete.")

if __name__ == "__main__":
    print("Start")
    main()
    