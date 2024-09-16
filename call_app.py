import asyncio
import os
from aiortc.contrib.media import MediaPlayer
from dotenv import load_dotenv
from app_common import CallAppEventHandler, setup_signal_handling
from call import Call
from tracks import BeepTrack, TestVideoStreamTrack

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)



async def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")

    # True - Read from and write to video file
    # False - Send dummy data tracks and playback via OpenCV and local speakers
    video_file = False

    
    #TODO: Add the join mechanics that tries both listen / call
    #for this to work the connection failed / listening failed event in the call.py
    #still need proper handling
    #Set to True to call a remote side that is waiting. Set to False to wait for the
    #remote side to connect
    listen = False

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
        #call.attach_track(BeepTrack())
    
    
    try:
        if listen:
            main_loop =  asyncio.create_task(call.listen(address))
        else:
            main_loop =  asyncio.create_task(call.call(address))
        setup_signal_handling(main_loop)
        await main_loop
        #TODO: The call doesn't shutdown correctly yet to trigger this message
        #instead it remains connected to the signaling server
        print("Call ended")
    except asyncio.CancelledError:
        #This should trigger when our exit signal (e.g. ctrl+c) is triggered
        print("CancelledError triggered. Starting controlled shutdown")
    finally:
        print("Shutting down...")
        await call.dispose()
        print("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
    