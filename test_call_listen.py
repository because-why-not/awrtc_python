import asyncio
import os

from call import Call


def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")

    call  = Call(uri)
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
    