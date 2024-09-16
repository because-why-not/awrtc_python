import asyncio
import os
from dotenv import load_dotenv
from app_common import CallAppEventHandler, setup_signal_handling
from call import Call
from tracks import BeepTrack, TestVideoStreamTrack
import logging
logging.basicConfig(level=logging.INFO)

load_dotenv()


async def main():
    uri = os.getenv('SIGNALING_CONFERENCE_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")
    
    call  = Call(uri, CallAppEventHandler(), True)
    call.attach_track(TestVideoStreamTrack())
    #call.attach_track(BeepTrack())
    
    try:
        main_loop =  asyncio.create_task(call.listen(address))
        setup_signal_handling(main_loop)
        await main_loop
        #this shouldn't be printed to the log. Calls in conference mode never exit
        #unless something breaks
        print("Main loop exited")
    except asyncio.CancelledError:
        #This should trigger when our exit signal (e.g. ctrl+c) is triggered
        print("CancelledError triggered. Starting controlled shutdown")
    finally:
        await call.dispose()
        print("shutdown complete.")



if __name__ == "__main__":
        asyncio.run(main())
    