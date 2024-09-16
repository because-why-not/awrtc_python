from typing import Dict, Optional
from call_events import CallEndedEventArgs, CallEventArgs
from prefix_logger import PrefixLogger, setup_logger
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
class Call(CallEventHandler):
    def __init__(self, uri, track_observer: CallEventHandler, is_conference = False):
        self.logger = setup_logger().get_child("Call")
        self.is_conference = is_conference
        self.uri = uri
        self.in_signaling = False
        self.listening = False
        self.track_observer = track_observer
        self.peers : Dict[int, CallPeer] = {}

        self.out_video_track : Optional[MediaStreamTrack]= None
        self.out_audio_track : Optional[MediaStreamTrack] = None
        
        self.network = WebsocketNetwork(self.logger)
        self.network.register_event_handler(self.signaling_event_handler)
        self.logger.info("call created")
    
    #these are call events triggered by CallPeer directly
    #we inspect them and then forward it to the user
    async def on_call_event(self, args: CallEventArgs):
        #TODO: If we have a 1 to 1 call we should cut the
        #signaling connection a few seconds after CallAccepted
        if isinstance(args, CallEndedEventArgs):
            peer = self.peers[args.connection_id.id]
            await peer.close()
            del self.peers[args.connection_id.id]
        #forward to user
        await self.track_observer.on_call_event(args)

    def createPeer(self, connectionId: ConnectionId):
        self.logger.info(f"Creating peer with id {connectionId}")
        peer = CallPeer(connectionId, self, self.logger)
        
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
        self.logger.error(f"Peer with id {connectionId} not found")
        return None

    def attach_track(self, track: MediaStreamTrack):
        if track.kind == "video":
            self.out_video_track = track
        else:
            self.out_audio_track = track

    async def on_peer_signaling_message(self, peer, msg: str):
        self.logger.debug(f"Sending: {msg}")
        await self.network.send_text(msg, peer.connection_id)

    async def listen(self, address):
        #connect to signaling server itself
        await self.network.start(self.uri)
        #wait for connection
        await self.network.listen(address)
        self.in_signaling = True
        #loop and wait for messages.
        #they are returned via the event handler
        await self.network.process_messages()

    async def call(self, address):
        #connect to signaling server itself
        await self.network.start(self.uri)
        #connect to another client waiting
        await self.network.connect(address)
        self.in_signaling = True
        #loop and wait for messages.
        #they are returned via the event handler
        await self.network.process_messages()
        
    def shutdown(self, reason = ""):
        self.logger.info(f"Shutting down. Reason: {reason}")
        self.in_signaling = False
        #todo: clean shutdown
        #self.network.shutdown()

    async def handle_message(self, message):
        self.logger.debug(f"Forwarding signaling message from peer: {message}")
        await self.network.send_text(message)
    
    async def signaling_event_handler(self, evt: NetworkEvent):    
        self.logger.debug(f"Received event of type {evt.type}")
        if evt.type == NetEventType.NewConnection:
            self.logger.info("NewConnection event")
            peer = self.createPeer(evt.connection_id)
            
            #TODO: we need an event handler to 
            #manage all other signaling messages anyway. 
            #no need to give the offer special treatmeant via
            #its own call
            
            if self.is_conference:
                await peer.negotiate_role()
            elif self.listening == False:
                #by default new outgoing connections create an offer
                await peer.create_offer()
                
        elif evt.type == NetEventType.ConnectionFailed:
            #peer = self.getPeer(evt.connection_id)
            self.logger.warning(f"ConnectionFailed event {evt.connection_id}")
            
        elif evt.type == NetEventType.Disconnected:
            peer = self.getPeer(evt.connection_id)
            #For conference mode we expect signaling connections to remain open
            #to detect new users joining
            #for 1 to 1 we close them to reduce server load
            self.logger.info(f"Disconnected event {evt.connection_id}")
            if peer is not None:
                if self.is_conference:
                    await peer.close()
                #do nothing for 1 to 1 connections
                #TODO: Maybe close the peer if they didn't complete
                #signaling yet?
            
        elif evt.type == NetEventType.ServerInitialized:
            self.listening = True
        elif evt.type == NetEventType.ServerInitFailed:
            #
            self.logger.error("Listening failed")
        elif evt.type == NetEventType.ReliableMessageReceived:
            msg : str = evt.data_to_text()
            peer = self.getPeer(evt.connection_id)
            if peer:
                await peer.forward_message(msg)
            else:
                self.logger.warning(f"Message for unknown connection received id {evt.connection_id}")
    
    async def dispose(self):
        #close all peers. Note: Each peer triggers an CallEnded event when still open at this point
        #the event handler will remove them from the peer list
        for p in list(self.peers.values()):
            await p.close()
        await self.network.dispose()
