import asyncio
import json
import string
from typing import List
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCRtpTransceiver, MediaStreamTrack 
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.sdp import candidate_from_sdp

from unity import proc_local_sdp
DATA_CHANNEL_RELIABLE= "reliable"
DATA_CHANNEL_UNRELIABLE= "unreliable"

class CallPeer:
    def __init__(self, sending: string = None, recording: string = None):
        self.peer = RTCPeerConnection()
        self.recording = recording
        self.sending = sending
        self.recorder = None
        self.player = None
        self.out_video_track : MediaStreamTrack = None
        self.out_audio_track : MediaStreamTrack = None
        if sending:
            self.player = MediaPlayer(sending)
            self.out_video_track = self.player.video
            self.out_audio_track = self.player.audio

        self.dc_reliable : RTCDataChannel = None
        self.dc_unreliable : RTCDataChannel = None

        self.inc_video_track : MediaStreamTrack = None
        self.inc_audio_track : MediaStreamTrack = None

        self._observers = []
        # Setup peer connection event handlers
        self.peer.on("track", self.on_track)
        self.peer.on("connectionstatechange", self.on_connectionstatechange)
        self.peer.on("datachannel", self.on_data_channel)

    def on_data_channel(self, datachannel):
        print("received new data channel " + datachannel.label)
        if datachannel.label == DATA_CHANNEL_RELIABLE:
            self.dc_reliable = datachannel
        elif datachannel.label == DATA_CHANNEL_UNRELIABLE:
            self.dc_unreliable = datachannel


    def on_signaling_message(self, observer_function):
        self._observers.append(observer_function)

    async def trigger_on_signaling_message(self, message):
        for observer in self._observers:
            await observer(message)
    
    async def forward_message(self, msg: string):
        print("in msg: "+ msg)
        jobj = json.loads(msg)
        if isinstance(jobj, dict):
            if 'sdp' in jobj:
                await self.peer.setRemoteDescription(RTCSessionDescription(jobj["sdp"], jobj["type"]))
                print("setRemoteDescription done")
                if self.peer.signalingState == "have-remote-offer":
                    await self.create_answer()

            if 'candidate' in jobj:
                str_candidate = jobj.get("candidate")
                if str_candidate == "":
                    print("Empty ice candidate")
                    return
                candidate = candidate_from_sdp(str_candidate)
                candidate.sdpMid = jobj.get("sdpMid")
                candidate.sdpMLineIndex = jobj.get("sdpMLineIndex")
                
                await self.peer.addIceCandidate(candidate)
                print("addIceCandidate done")

    async def on_track(self, track):
        print("Track received:", track.kind)
        if track.kind == "audio":
            self.inc_audio_track = track
        elif track.kind == "video":
            self.inc_video_track = track

        if self.recording:
            await self.start_recording(self.recording, self.inc_audio_track, self.inc_video_track)

    def on_connectionstatechange(self):
        print("Connection state changed:", self.peer.connectionState)

    
    def setup_transceivers(self):
        if self.sending:
            if self.videoTransceiver is not None and self.out_video_track is not None:
                self.videoTransceiver.sender.replaceTrack(self.out_video_track)
                self.videoTransceiver.direction = "sendrecv"
            if self.audioTransceiver is not None and self.out_audio_track is not None:
                self.audioTransceiver.sender.replaceTrack(self.out_audio_track)
                self.audioTransceiver.direction = "sendrecv"

    async def create_offer(self):

        self.dc_reliable = self.peer.createDataChannel(label=DATA_CHANNEL_RELIABLE)
        self.dc_unreliable = self.peer.createDataChannel(label=DATA_CHANNEL_UNRELIABLE)

        self.audioTransceiver = self.peer.addTransceiver("audio", direction="sendrecv") 
        self.videoTransceiver = self.peer.addTransceiver("video", direction="sendrecv")
        self.setup_transceivers()

        offer = await self.peer.createOffer()
        print("Offer created")
        await self.peer.setLocalDescription(offer)
        offer_w_ice = self.sdpToText(self.peer.localDescription.sdp, "offer")
        print(offer_w_ice)
        return offer_w_ice

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
            print("Offer side might be incompatible. Expected 2 transceivers but found " + len(transceivers))

        self.videoTransceiver = CallPeer.find_first(transceivers, "video")
        if self.videoTransceiver is None: 
            print("No video transceiver found. The remote side is likely incompatible")

        self.audioTransceiver = CallPeer.find_first(transceivers, "audio")
        if self.audioTransceiver is None: 
            print("No audio transceiver found. The remote side is likely incompatible")
        
        self.setup_transceivers()
            
        answer = await self.peer.createAnswer()
        await self.peer.setLocalDescription(answer)
        text_answer = self.sdpToText(self.peer.localDescription.sdp, "answer")
        await self.trigger_on_signaling_message(text_answer)

    async def set_remote_description(self, sdp, type_):
        description = RTCSessionDescription(sdp, type_)
        await self.peer.setRemoteDescription(description)
        print("Remote description set")

    async def add_ice_candidate(self, candidate):
        await self.peer.addIceCandidate(candidate)

    async def start_recording(self, filename, atrack, vtrack):
        print("Recording setup")
        self.recorder = MediaRecorder(filename)
        if atrack:
            self.recorder.addTrack(atrack)
        if vtrack:
            self.recorder.addTrack(vtrack)

        await self.recorder.start()
        print("Recording started")

    async def stop_recording(self):
        if self.recorder:
            await self.recorder.stop()
            print("Recording stopped")
    
    async def dispose(self):
        await self.stop_recording()
        await self.peer.close()