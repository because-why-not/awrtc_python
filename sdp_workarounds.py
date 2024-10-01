from tools import filter_vp8_codec

#There is a compatibility issue between aiortc and the WebRTC Video Chat unity plugin
#which stops the peer from connecting. For now this workaround fixes the issue but this
#needs further testing with newer versions of both.
def proc_local_sdp(sdp: str):
    #no changes
    sdp_res = sdp
    #aiortc1.5
    #sdp_res = sdp.replace("a=extmap:2 urn:ietf:params:rtp-hdrext:ssrc-audio-level", "a=extmap:3 urn:ietf:params:rtp-hdrext:ssrc-audio-level")
    #this forces VP8.
    #sdp_res = filter_vp8_codec(sdp_res)
    return sdp_res