from enum import Enum
import asyncio
from websocket_network import WebsocketNetwork, NetworkEvent, NetEventType

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer
import json
import time
import logging
import re
from aiortc import RTCRtpReceiver, RTCRtpTransceiver
import cv2

## ENABLE THIS LINE TO SEE DETAILED DEBUG LOGS IN THE TERMINAL
# logging.basicConfig(level=logging.DEBUG)


uri = 'ws://IP_ADDRESS_SERVER:PORT_NO/callapp'
ROOM_NAME = 'abc123'
video_h = 1920
video_w = 1080
fps = 30
file_path = 'video_recorded/recording1.mp4'
MAX_FRAMES = 600


configuration = RTCConfiguration(
    iceServers=[
        RTCIceServer(urls='stun:stun.l.google.com:19302'),
		RTCIceServer(urls='stun:stun1.l.google.com:19302'),
        RTCIceServer(urls='stun:stun2.l.google.com:19302'),
        RTCIceServer(urls='stun:stun3.l.google.com:19302'),
        RTCIceServer(urls='stun:stun4.l.google.com:19302'),
        RTCIceServer(
            urls='turn:t.y-not.app:443',
            username='user_nov',
            credential='pass_nov'
        )
    ]
)



network : WebsocketNetwork = None


peer = RTCPeerConnection(configuration)
global dc1
dc1 = None
global dc2
dc2 = None

global setting_remote
setting_remote = False

global message_buffer
message_buffer = []


def extract_codecs(sdp):
    lines = sdp.split('\n')
    audio_codecs = []
    video_codecs = []
    current_media = None

    for line in lines:
        line = line.strip()
        

        if line.startswith('m=audio'):
            current_media = 'audio'
        elif line.startswith('m=video'):
            current_media = 'video'

        if line.startswith('a=rtpmap:'):
            codec = line.split(' ')[1]#.split('/')[0]
            if current_media == 'audio':
                audio_codecs.append(codec)
            elif current_media == 'video':
                video_codecs.append(codec)

    return audio_codecs, video_codecs



def parse_ice_candidate(candidate, sdpMid, sdpMLineIndex):
    ## this function doesn't work very well!!
    m = re.match(r'candidate:(\S+) (\d) (\S+) (\d+) (\S+) (\d+) typ (\S+)', candidate)
    if not m:
        raise ValueError('Invalid candidate')
    return RTCIceCandidate(
        foundation=m.group(1),
        component=m.group(2),
        protocol=m.group(3),
        priority=int(m.group(4)),
        ip=m.group(5),
        port=int(m.group(6)),
        type=m.group(7),
        # tcpType=m.group(9) if 'tcptype' in candidate else None,

        sdpMid=sdpMid,
        sdpMLineIndex=sdpMLineIndex
    )

async def handle_video_track(track):
    nframe = 0
    start_time = time.time()
    # fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
    # writer = cv2.VideoWriter(file_path, fourcc, fps, (video_w, video_h))
    prev_frame_time = 1

    while True:
        if not peer.connectionState == "connected":
            print('peer connectionstate :', peer.connectionState)
            time.sleep(0.5)
            frame = await track.recv()

            continue
        frame = await track.recv()
        
        # Convert the frame to a numpy array
        img = frame.to_ndarray(format="bgr24")

        # THIS PART ALLOWS TO SAVE THE FEED AS VIDEO
        # if nframe<MAX_FRAMES:
        #     writer.write(img)
        # else:
        #     print('release video writer')
        #     writer.release()

        # Print the shape of the frame
        # if peer._iceConnection.state == 'completed' or peer._iceConnection.state == 'failed':
        #     pair = peer._iceConnection.selected_pair
        #     print(pair)
             
        # print(img.shape, nframe/(time.time()-start_time), peer.connectionState )

        # print('Average Frame rate: ', nframe/(time.time()-start_time) )
        print(img.shape,'Current Frame rate: ', 1/(time.time()-prev_frame_time), ' Average Frame rate: ', nframe/(time.time()-start_time) )
        prev_frame_time = time.time()

        nframe +=  1


        # Optionally, you can display the video frame using OpenCV
        # cv2.imshow('Video Frame', img)
        # cv2.waitKey(1)



def append_candidate(sdp, candidate):
    sdp += 'a={}\r\n'.format(candidate)
    return sdp

def convert_json_to_sdp(json_messages):
    for msg in json_messages:
        if 'sdp' in msg:
            sdp_buffer = msg['sdp']
        if 'candidate' in msg:
            sdp_buffer = append_candidate(sdp_buffer, msg['candidate'])
    return sdp_buffer



async def create_offer():
    global dc1
    global dc2


    dc1 = peer.createDataChannel(label="reliable")
    dc2 = peer.createDataChannel(label="unreliable")
    
    peer.addTransceiver("audio", direction="recvonly")  # if you want to receive audio
    peer.addTransceiver("video", direction="recvonly")  # if you want to receive video

    
    @peer.on("track")
    def on_track(track):
        print("=================> on_track=================== ", track.kind)
        if track.kind == "video":
            print("Video track was added")
            # Handle video track (e.g., attaching to a media player, etc.)
            asyncio.ensure_future(handle_video_track(track))

        elif track.kind == "audio":
            print("Audio track was added")
            # Handle audio track

    @dc1.on("message")
    def on_message(message):

        message = message.decode('utf-8')
        print("dc1", message)
    @dc2.on("message")
    def on_message(message):
        print("dc2", message)




    offer = await peer.createOffer()
    await peer.setLocalDescription(offer)
    data = {"sdp":peer.localDescription.sdp, "type":"offer"}
    offer_w_ice =  json.dumps(data)
    # print(offer_w_ice)
    return offer_w_ice

async def my_event_handler(evt: NetworkEvent):
    
    print(f"Received event of type {evt.type}")
    if evt.type == NetEventType.NewConnection:
        # got connected. For now we assume the remote side is already in the waiting state
        # this means we can just send an offer

        test_offer = await create_offer()
        # print("sending : " + test_offer)
        await network.send_text(test_offer)

    if evt.type == NetEventType.ReliableMessageReceived:
        # we received a message from the other end. The other side will send a random number in case we need to negotiate
        # who is suppose to send an offer. 
        # all other messages should be answer & ice candidates
        global message_buffer
        msg = evt.data_to_text()
        # print("in msg: "+ msg)
        global setting_remote
        if 'sdp' in msg and setting_remote == False:
            setting_remote = True
            json_msg = json.loads(msg)
            print("====================> SDP received... Printing supported codecs")
            
            audio, video = extract_codecs(json_msg.get('sdp'))
            print("Audio Codecs:", audio)
            print("Video Codecs:", video)
            

            await peer.setRemoteDescription(RTCSessionDescription(json_msg["sdp"], json_msg["type"]))


        if 'candidate' in msg:
            candidate_dict = json.loads(msg)
            candidate_split = candidate_dict.get("candidate").split()
            protocol = candidate_split[2]
            type = candidate_split[7]
            print(" ============> Candidate protocol", protocol, " type:", type)
            # if type == "host":
            #     return
            try:
                candidate = RTCIceCandidate(
                    component=candidate_dict.get("sdpMLineIndex"),
                    foundation=candidate_dict.get("candidate").split()[0],
                    ip=candidate_dict.get("candidate").split()[4],
                    port=int(candidate_dict.get("candidate").split()[5]),
                    priority=int(candidate_dict.get("candidate").split()[3]),
                    protocol=candidate_dict.get("candidate").split()[2],
                    relatedAddress=candidate_dict.get("candidate").split()[9] if 'raddr' in candidate_dict.get("candidate") else None,
                    relatedPort=int(candidate_dict.get("candidate").split()[11]) if 'rport' in candidate_dict.get("candidate") else None,
                    tcpType=candidate_dict.get("candidate").split()[9] if 'tcptype' in candidate_dict.get("candidate") else None,
                    type=candidate_dict.get("candidate").split()[7] if 'typ' in candidate_dict.get("candidate") else None,
                )
                # print(candidate_dict)

                candidate.sdpMid = candidate_dict.get("sdpMid")
                candidate.sdpMLineIndex = candidate_dict.get("sdpMLineIndex")

                # candidate_parsed = parse_ice_candidate(candidate_dict.get("candidate"), candidate_dict.get("sdpMid"), candidate_dict.get("sdpMLineIndex"))
                # print("====================> Parsed candidate : ")
                # print(candidate_parsed)
                # await peer.addIceCandidate(candidate_parsed)
                await peer.addIceCandidate(candidate)

            except Exception as e:
                print("error while parsing candidate:", e)
                print(candidate_dict)
                return

        '''
        if 'sdp' in msg or 'candidate' in msg:
            message_buffer.append(msg)
        
        if len(message_buffer) == 4:
            json_messages = []
            for msg in message_buffer:
                json_messages.append(json.loads(msg))

            sdp = convert_json_to_sdp(json_messages)
        '''



async def dummy_task():
    while True:
        await asyncio.sleep(10) 

async def run_signaling():
    global network
    network = WebsocketNetwork()
    network.register_event_handler(my_event_handler)
    #connect to signaling server itself
    await network.start(uri)
    #connect indirectly to unity client through the server
    await network.connect(ROOM_NAME)
    #loop and wait for messages
    while(True):
        await network.next_message()

async def main():
    
    task1 = asyncio.ensure_future(run_signaling())
    #place holder for other task
    task2 = asyncio.ensure_future(dummy_task())
    await asyncio.gather(task1, task2)

if __name__ == "__main__":
    print("Start")
    print("Printing the video capabilities: ")
    print(RTCRtpReceiver.getCapabilities("video").codecs)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
    
    