from enum import Enum
import time
import asyncio
import json
import os
from websocket_network import WebsocketNetwork, NetworkEvent, NetEventType
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate

from aiortc.contrib.media import MediaRecorder, MediaPlayer

from tools import filter_vp8_codec
from aiortc.sdp import candidate_from_sdp
from dotenv import load_dotenv
from call_peer import CallPeer
load_dotenv()

'''
Prototype Call implementation similar to Unity ICall and BrowserCall for web. 
* So it will send a video based on a file and will write the received video to a file
    (see CallPeer init below)
* Only 1 peer
* The remote side must already wait for an incoming call
'''
class Call:
    def __init__(self, uri):
        self.network : WebsocketNetwork = None
        self.uri = uri
        self.in_signaling = False
        self.peer = CallPeer("video.mp4", "incoming.mp4")
        #todo: event handler to deal with offer,answer and ice candidates
        #self.peer.register_event_handler(self.peer_signaling_event_handler)
    
    async def start(self, address):
        self.network = WebsocketNetwork()
        self.network.register_event_handler(self.signaling_event_handler)
        #connect to signaling server itself
        await self.network.start(self.uri)
        #connect indirectly to unity client through the server
        await self.network.connect(address)
        self.in_signaling = True
        #loop and wait for messages.
        #they are returned via the event handler
        #todo: remove this manual loop?
        while(self.in_signaling):
            await self.network.next_message()
        
    def shutdown(self, reason = ""):
        print("Shutting down. Reason: " + reason)
        self.in_signaling = False
        #todo: clean shutdown
        #self.network.shutdown()

    
    async def signaling_event_handler(self, evt: NetworkEvent):    
        print(f"Received event of type {evt.type}")
        if evt.type == NetEventType.NewConnection:
            print("NewConnection event")
            #TODO: we need an event handler to 
            #manage all other signaling messages anway. 
            #no need to give the offer special treatmeant via
            #its own call
            offer = await self.peer.create_offer()
            print("sending : " + offer)
            await self.network.send_text(offer)

        if evt.type == NetEventType.ConnectionFailed:
            print("ConnectionFailed event")
            self.shutdown("ConnectionFailed event from signaling")
            

        if evt.type == NetEventType.ReliableMessageReceived:
            msg : str = evt.data_to_text()
            await self.peer.forward_message(msg)
    
    async def dispose(self):
        if self.peer:
            await self.peer.dispose()


def main():
    uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
    address = os.getenv('ADDRESS', "abc123")

    call  = Call(uri)
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(call.start(address))
    except KeyboardInterrupt:
        pass
    finally:        
        print("Shutting down...")
        loop.run_until_complete(call.dispose())
        print("shutdown complete.")

if __name__ == "__main__":
    print("Start")
    main()
    