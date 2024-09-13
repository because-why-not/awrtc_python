from abc import abstractmethod
import asyncio
import os
from typing import Optional
from aiortc.contrib.media import MediaPlayer
from dotenv import load_dotenv
from app_common import CallAppEventHandler, FileStreaming, LocalPlayack, TracksProcessor
from call import Call
from call_events import CallEventArgs, CallEventType, TrackUpdateEventArgs
from call_peer import CallEventHandler
from tracks import BeepTrack, TestVideoStreamTrack

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)



def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")

    # True - Read from a video file and write to a video file
    # False - Send dummy data tracks and playback via OpenCV and local speakers
    video_file = False



    sending = "video.mp4"
    receiving = "inc.mp4"
    if video_file:
        track_handler = CallAppEventHandler(receiving)
    else:
        track_handler = CallAppEventHandler()
    



    call  = Call(uri, track_handler)

    if video_file:
        player = MediaPlayer(sending, loop=True)
        call.attach_track(player.video)
        call.attach_track(player.audio)
    else:
        call.attach_track(TestVideoStreamTrack())
        call.attach_track(BeepTrack())
        
        



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
    