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
load_dotenv()

uri = os.getenv('SIGNALING_URI', 'ws://192.168.1.3:12776')
address = os.getenv('ADDRESS', "abc123")
print(uri)
print(address)



class TestWebsocketNetwork:
    
    def __init__(self, name):
        self.name = name
        self.network : WebsocketNetwork = WebsocketNetwork()
        self.network.register_event_handler(self.my_event_handler)
        self.running = True

    async def my_event_handler(self, evt: NetworkEvent):
        
        print(f"{self.name}: Received event of type {evt.type}")
        if evt.type == NetEventType.NewConnection:
            msg = "Hello World"
            print(f"{self.name}: sending message: {msg}")
            
            await self.network.send_text(msg, evt.connection_id)
        if evt.type == NetEventType.ConnectionFailed:
            print(f"{self.name}: error")
            self.running = False
        if evt.type == NetEventType.Disconnected:
            print(f"{self.name}: error")
            self.running = False

        if evt.type == NetEventType.ReliableMessageReceived:
            # we received a message from the other end. The other side will send a random number in case we need to negotiate
            # who is suppose to send an offer. 
            # all other messages should be answer & ice candidates
            global message_buffer
            msg : str = evt.data_to_text()
            print(f"{self.name}: message received: {msg}")
            self.running = False
            
    async def run_listening(self, uri, address):
        await self.network.start(uri)
        #connect indirectly to unity client through the server
        print(f"{self.name}: listening")
        await self.network.listen(address)
        #loop and wait for messages
        while(self.running):
            await self.network.next_message()
        print("{self.name}: stopped running")

    async def run_connecting(self, uri, address):
        await asyncio.sleep(1.0) 
        await self.network.start(uri)
        #connect indirectly to unity client through the server
        print(f"{self.name}: connecting")
        await self.network.connect(address)
        #loop and wait for messages
        while(self.running):
            await self.network.next_message()
        print("{self.name}: stopped running")

async def main():


    test1 = TestWebsocketNetwork("L ")
    test2 = TestWebsocketNetwork("S ")
    
    task1 = asyncio.ensure_future(test1.run_listening(uri, address))

    task2 = asyncio.ensure_future(test2.run_connecting(uri, address))
    
    await asyncio.gather(task1, task2)

if __name__ == "__main__":
    print("Start")
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:        
        print("Shutting down...")
    



