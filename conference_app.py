import asyncio
import os
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from dotenv import load_dotenv
from aiortc import VideoStreamTrack
from aiortc.mediastreams import AudioStreamTrack
from app_common import CallAppEventHandler
from call import Call
from call_peer import CallEventHandler, OldCallEventHandler
from tracks import BeepTrack, TestVideoStreamTrack

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)


def main():
    uri = os.getenv('SIGNALING_CONFERENCE_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")
    
    
    call  = Call(uri, CallAppEventHandler(), True)
    call.attach_track(TestVideoStreamTrack())
    call.attach_track(BeepTrack())
    


    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(call.listen(address))
    except KeyboardInterrupt:
        pass
    finally:        
        print("Shutting down...")
        loop.run_until_complete(call.dispose())
        print("shutdown complete.")

if __name__ == "__main__":
    print("Start")
    main()
    