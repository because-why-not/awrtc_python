import asyncio
import json
import string
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.sdp import candidate_from_sdp

from unity import proc_local_sdp

class CallPeer:
    def __init__(self, sending: string = None, recording: string = None):
        self.peer = RTCPeerConnection()
        self.recording = recording
        self.sending = sending
        self.recorder = None
        self.player = None
        if sending:
            self.player = MediaPlayer(sending)

        self.dc_reliable : RTCDataChannel = None
        self.dc_unreliable : RTCDataChannel = None

        self.inc_video_track = None
        self.inc_audio_track = None

        # Setup peer connection event handlers
        self.peer.on("track", self.on_track)
        self.peer.on("connectionstatechange", self.on_connectionstatechange)


    async def forward_message(self, msg: string):
        print("in msg: "+ msg)
        jobj = json.loads(msg)
        if isinstance(jobj, dict):
            if 'sdp' in jobj:
                await self.peer.setRemoteDescription(RTCSessionDescription(jobj["sdp"], jobj["type"]))
                print("setRemoteDescription done")
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

    async def create_offer(self):

        self.dc_reliable = self.peer.createDataChannel(label="reliable")
        self.dc_unreliable = self.peer.createDataChannel(label="unreliable")

        self.audioTransceiver = self.peer.addTransceiver("audio", direction="sendrecv") 
        self.videoTransceiver = self.peer.addTransceiver("video", direction="sendrecv")

        if self.sending:
            player = MediaPlayer('video.mp4')
            self.videoTransceiver.sender.replaceTrack(player.video)
            self.audioTransceiver.sender.replaceTrack(player.audio)

        offer = await self.peer.createOffer()
        print("Offer created")
        await self.peer.setLocalDescription(offer)
        sdp = proc_local_sdp(self.peer.localDescription.sdp)
        
        data = {"sdp":sdp, "type":"offer"}
        offer_w_ice =  json.dumps(data)
        print(offer_w_ice)
        return offer_w_ice

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