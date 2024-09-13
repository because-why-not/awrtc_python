import random
from typing import Dict, Optional
from websocket_network import ConnectionId, WebsocketNetwork, NetworkEvent, NetEventType
from aiortc import MediaStreamTrack

from call_peer import CallPeer, CallEventHandler




'''
Prototype Call implementation similar to Unity ICall and BrowserCall for web. 
* So it will send a video based on a file and will write the received video to a file
    (see CallPeer init below)
* Only 1 peer
* The remote side must already wait for an incoming call
'''
class Call:
    def __init__(self, uri, track_observer: CallEventHandler, isConference = False):
        self.mIsConference = isConference
        self.network : WebsocketNetwork
        self.uri = uri
        self.in_signaling = False
        self.listening = False
        self.track_observer = track_observer
        self.peers : Dict[int, CallPeer] = {}
    
    def createPeer(self, connectionId: ConnectionId):
        
        print("creating peer with id " + str(connectionId))
        peer = CallPeer(connectionId, self.track_observer)
        
        peer.on_signaling_message(self.on_peer_signaling_message)
        
        if self.out_video_track:
            peer.attach_track(self.out_video_track)
        if self.out_audio_track:
            peer.attach_track(self.out_audio_track)
        self.peers[connectionId.id] = peer
        return peer
    
    def getPeer(self, connectionId: ConnectionId):
        if connectionId.id in self.peers:
            return self.peers[connectionId.id]
        print("error: peer with id " + str(connectionId) + " not found")
        return None

    def attach_track(self, track: MediaStreamTrack):
        if track.kind == "video":
            self.out_video_track = track
        else:
            self.out_audio_track = track
        

    async def on_peer_signaling_message(self, peer, msg: str):
        print("sending " + msg)
        await self.network.send_text(msg, peer.connection_id)

    async def listen(self, address):
        self.network = WebsocketNetwork()
        self.network.register_event_handler(self.signaling_event_handler)
        #connect to signaling server itself
        await self.network.start(self.uri)
        #connect indirectly to unity client through the server
        await self.network.listen(address)
        self.in_signaling = True
        #loop and wait for messages.
        #they are returned via the event handler
        await self.network.process_messages()

    async def call(self, address):
        self.network = WebsocketNetwork()
        self.network.register_event_handler(self.signaling_event_handler)
        #connect to signaling server itself
        await self.network.start(self.uri)
        #connect indirectly to unity client through the server
        await self.network.connect(address)
        self.in_signaling = True
        #loop and wait for messages.
        #they are returned via the event handler
        await self.network.process_messages()
        
    def shutdown(self, reason = ""):
        print("Shutting down. Reason: " + reason)
        self.in_signaling = False
        #todo: clean shutdown
        #self.network.shutdown()

    async def handle_message(self, message):
        print(f"forwarding signaling message from peer: {message}")
        await self.network.send_text(message)

    
    async def signaling_event_handler(self, evt: NetworkEvent):    
        print(f"Received event of type {evt.type}")
        if evt.type == NetEventType.NewConnection:
            print("NewConnection event")
            peer = self.createPeer(evt.connection_id)
            
            #TODO: we need an event handler to 
            #manage all other signaling messages anyway. 
            #no need to give the offer special treatmeant via
            #its own call
            
            if self.mIsConference:
                await peer.negotiate_role()
            elif self.listening == False:
                #by default new outgoing connections create an offer
                await peer.create_offer()
                
        elif evt.type == NetEventType.ConnectionFailed:
            peer = self.getPeer(evt.connection_id)
            print("ConnectionFailed event " + str(evt.connection_id))
            
        elif evt.type == NetEventType.ServerInitialized:
            self.listening = True
        elif evt.type == NetEventType.ServerInitFailed:
            #
            print("Listening failed")
        elif evt.type == NetEventType.ReliableMessageReceived:
            msg : str = evt.data_to_text()
            peer = self.getPeer(evt.connection_id)
            if peer:
                await peer.forward_message(msg)
            else:
                print("message for unknown connect received id " + str(evt.connection_id))
    
    async def dispose(self):
        for p in self.peers.values():
            await p.dispose()

