import asyncio
import json
import random
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, List, Optional
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCRtpTransceiver, MediaStreamTrack 
from aiortc.contrib.media import MediaPlayer
from aiortc.sdp import candidate_from_sdp
from call_events import CallAcceptedEventArgs, CallEndedEventArgs, CallEventArgs, CallEventType, TrackUpdateEventArgs
from websocket_network import ConnectionId
from sdp_workarounds import proc_local_sdp
from prefix_logger import PrefixLogger

DATA_CHANNEL_RELIABLE= "reliable"
DATA_CHANNEL_UNRELIABLE= "unreliable"

class CallEventHandler(ABC):
    @abstractmethod
    async def on_call_event(self, args: CallEventArgs):
        pass

class OldCallEventHandler(CallEventHandler):
    
    @abstractmethod
    async def on_start(self):
        pass
    @abstractmethod
    async def on_stop(self):
        pass

    @abstractmethod
    def on_track(self, track):
        pass
    
    async def on_call_event(self, args: CallEventArgs):
        if args.type == CallEventType.CALL_ACCEPTED:
            await self.on_start()
        elif args.type == CallEventType.CALL_ENDED:
            await self.on_stop()
        elif isinstance(args, TrackUpdateEventArgs):
            self.on_track(args.track)
        

SignalingCallback = Callable[['CallPeer', str], Awaitable[None]]
class CallPeer:
    

    def __init__(self, connection_id : ConnectionId, track_observer: CallEventHandler, logger: PrefixLogger):
        self.logger = logger.get_child("CallPeer" + str(connection_id.id))
        self.peer = RTCPeerConnection()
        self.connection_id = connection_id
        self.random_number : int
        self.track_observer : CallEventHandler = track_observer
        self.dc_reliable : RTCDataChannel
        self.dc_unreliable : RTCDataChannel

        self.out_video_track : Optional[MediaStreamTrack] = None
        self.out_audio_track : Optional[MediaStreamTrack] = None
        self.inc_video_track : Optional[MediaStreamTrack] = None
        self.inc_audio_track : Optional[MediaStreamTrack] = None

        self.has_ended = False

        self._observers:list[SignalingCallback] = []
        # Setup peer connection event handlers
        self.peer.on("track", self.on_track)
        self.peer.on("connectionstatechange", self.on_connectionstatechange)
        #self.peer.on("iceconnectionstatechange", self.on_iceConnectionState)        
        self.peer.on("datachannel", self.on_data_channel)

    def attach_track(self, track: MediaStreamTrack):
        if track.kind == "video":
            self.out_video_track = track
        else:
            self.out_audio_track = track

    def on_data_channel(self, datachannel):
        self.logger.info(f"Received new data channel {datachannel.label}")
        if datachannel.label == DATA_CHANNEL_RELIABLE:
            self.dc_reliable = datachannel
        elif datachannel.label == DATA_CHANNEL_UNRELIABLE:
            self.dc_unreliable = datachannel

    def on_signaling_message(self, observer_function: SignalingCallback):
        self._observers.append(observer_function)

    async def trigger_on_signaling_message(self, message: str):
        
        self.logger.info(f"SIG OUT: {message}")
        for observer in self._observers:
            await observer(self, message)
    
    async def forward_message(self, msg: str):
        self.logger.info(f"SIG IN : {msg}")
        try:
            jobj = json.loads(msg)
            if isinstance(jobj, dict):
                if 'sdp' in jobj:
                    await self.peer.setRemoteDescription(RTCSessionDescription(jobj["sdp"], jobj["type"]))
                    self.logger.info("setRemoteDescription done")
                    if self.peer.signalingState == "have-remote-offer":
                        await self.create_answer()

                elif 'candidate' in jobj:
                    str_candidate = jobj.get("candidate")
                    if str_candidate is not None:
                        if str_candidate == "":
                            self.logger.info("Empty ice candidate")
                            return
                        candidate = candidate_from_sdp(str_candidate)
                        candidate.sdpMid = jobj.get("sdpMid")
                        candidate.sdpMLineIndex = jobj.get("sdpMLineIndex")
                        await self.peer.addIceCandidate(candidate)
                        self.logger.debug(f"addIceCandidate done for: {str_candidate}")
                    else:
                        self.logger.warning(f"Invalid candidate message: {msg}")
                else:
                    self.logger.error(f"Unexpected JSON object received: {msg}")
            elif isinstance(jobj, int):
                #if needed we compare our random numbers and decide who sends out the offer
                #if not needed we already have created an offer and signalingState is "have-local-offer""
                self.logger.info(f"Random number received: {jobj}")
                if self.peer.signalingState == "stable" and int(self.random_number) > jobj:
                    await self.create_offer()

        except json.JSONDecodeError:
            # If it's not valid JSON, check if it's an integer
            if msg.isdigit():
                integer_value = int(msg)
                self.logger.info(f"Received an integer: {integer_value}")
                # Handle the integer case here
                # For example:
                # await self.handle_integer_message(integer_value)
            else:
                self.logger.error(f"Received message is neither valid JSON nor an integer: {msg}")
                # Handle the error case here, maybe raise an exception or log an error
        #check if it is just a single integer
        
        self.logger.debug("Message processing done")

    async def on_track(self, track):
        self.logger.info(f"Track received: {track.kind}")
        if track.kind == "audio":
            self.inc_audio_track = track
        elif track.kind == "video":
            self.inc_video_track = track
        
        await self.trigger_event(TrackUpdateEventArgs(self.connection_id, track))
            

    async def trigger_event(self, args: CallEventArgs):
        if self.track_observer:
            await self.track_observer.on_call_event(args)

    async def on_connectionstatechange(self):
        self.logger.info(f"Connection state changed: {self.peer.connectionState}")
        if self.peer.connectionState == "connected":
            await self.trigger_event(CallAcceptedEventArgs(self.connection_id))
        elif self.peer.connectionState == "failed":
            await self.trigger_ended()
        elif self.peer.connectionState == "closed":
            await self.trigger_ended()

    #catch all shutdown either because network closed, user stopped it or some error happened
    async def trigger_ended(self):
            if self.has_ended == False:
                self.logger.info("Peer connection has ended")
                self.has_ended = True
                await self.trigger_event(CallEndedEventArgs(self.connection_id))

    
    def setup_transceivers(self):
        if self.videoTransceiver is not None and self.out_video_track is not None:
            self.videoTransceiver.sender.replaceTrack(self.out_video_track)
            self.videoTransceiver.direction = "sendrecv"
        if self.audioTransceiver is not None and self.out_audio_track is not None:
            self.audioTransceiver.sender.replaceTrack(self.out_audio_track)
            self.audioTransceiver.direction = "sendrecv"

    async def negotiate_role(self):
        #send random number in case offer/answer role is unclear
        self.random_number = random.randint(1, 2**31 - 1)
        neg = str(self.random_number)
        self.logger.info(f"Sending random number: {neg}")
        await self.trigger_on_signaling_message(neg)
        
    async def create_offer(self):

        self.dc_reliable = self.peer.createDataChannel(label=DATA_CHANNEL_RELIABLE)
        self.dc_unreliable = self.peer.createDataChannel(label=DATA_CHANNEL_UNRELIABLE)

        self.audioTransceiver = self.peer.addTransceiver("audio", direction="sendrecv") 
        self.videoTransceiver = self.peer.addTransceiver("video", direction="sendrecv")
        self.setup_transceivers()

        offer = await self.peer.createOffer()
        self.logger.info("Offer created")
        await self.peer.setLocalDescription(offer)
        offer_w_ice = self.sdpToText(self.peer.localDescription.sdp, "offer")
        self.logger.info(f"Offer with ICE: {offer_w_ice}")
        
        await self.trigger_on_signaling_message(offer_w_ice)
        #return offer_w_ice

    def sdpToText(self, sdp, sdp_type):
        proc_sdp = proc_local_sdp(sdp)
        data = {"sdp":proc_sdp, "type": sdp_type}
        text =  json.dumps(data)
        return text

    @staticmethod
    def find_first(media_list : List[RTCRtpTransceiver], kind: str):
        for media in media_list:
            if media.kind == kind:
                return media
        return None 
    
    async def create_answer(self):
        #TODO: we must attach our tracks to the transceiver!!!
        #!!!!
        transceivers = self.peer.getTransceivers()
        if len(transceivers) != 2: 
            #this will likely crash later
            self.logger.warning(f"Offer side might be incompatible. Expected 2 transceivers but found {len(transceivers)}")

        self.videoTransceiver = CallPeer.find_first(transceivers, "video")
        if self.videoTransceiver is None: 
            self.logger.warning("No video transceiver found. The remote side is likely incompatible")

        self.audioTransceiver = CallPeer.find_first(transceivers, "audio")
        if self.audioTransceiver is None: 
            self.logger.warning("No audio transceiver found. The remote side is likely incompatible")
        
        self.setup_transceivers()
            
        answer : Optional[RTCSessionDescription] = await self.peer.createAnswer()
        if answer is None:
            self.logger.error("Error creating answer returned none")
            return
        await self.peer.setLocalDescription(answer)
        text_answer = self.sdpToText(self.peer.localDescription.sdp, "answer")
        await self.trigger_on_signaling_message(text_answer)

    async def set_remote_description(self, sdp, type_):
        description = RTCSessionDescription(sdp, type_)
        await self.peer.setRemoteDescription(description)
        self.logger.info("Remote description set")

    async def add_ice_candidate(self, candidate):
        await self.peer.addIceCandidate(candidate)
    
    async def close(self):
        await self.trigger_ended()
        self.logger.info("Calling close")
        try:
            await self.peer.close()
        except asyncio.CancelledError:
            self.logger.error("Peer connection triggered a CancelledError on close")
        except Exception as e:
            self.logger.error(f"Peer connection triggered an exception on close: {str(e)}")
            
        self.logger.info("Peer closed")