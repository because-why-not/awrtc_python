import asyncio
import os

from dotenv import load_dotenv
from app_common import CallAppEventHandler, get_tracks_from_args, parse_args, setup_signal_handling
from call import Call
import logging
logging.basicConfig(level=logging.INFO)



async def main():

    load_dotenv()
    args = parse_args()
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
        
    
    #TODO: Add the join mechanics that tries both listen / call
    #for this to work the connection failed / listening failed event in the call.py
    #still need proper handling
    #Set to True to call a remote side that is waiting. Set to False to wait for the
    #remote side to connect
    listen = args.listen
    
    #address used to connect
    address = args.address

    #either gets tracks from the --from-file flag or from --video / --audio
    video_track, audio_track = get_tracks_from_args(args)
    
    track_handler = CallAppEventHandler(args.to_file)
    call  = Call(uri, track_handler)
    
    if video_track:
        call.attach_track(video_track)
    
    if audio_track:
        call.attach_track(audio_track)
    
    
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
    