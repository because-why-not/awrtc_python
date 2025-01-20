# awrtc_python

## Introduction 
Use this project to create a Python server or client for live video and audio streaming applications compatible with the Unity Asset "WebRTC Video Chat" ([available on Unity Asset Store](https://assetstore.unity.com/packages/tools/network/webrtc-video-chat-68030)) or awrtc_browser ([github](https://github.com/because-why-not/awrtc_browser)).


## Setup
Install all pip modules via:
   ```
   pip install -r requirements.txt
   ```
Then copy `example_.env` to `.env` and change the URLs to your own servers if needed.

The default values will use a free test server shared with Unity and browser side exampes.
   
To learn how to set up your own signaling server, see:
- awrtc_signaling [github](https://github.com/because-why-not/awrtc_signaling)
- awrtc_signaling for docker: [awrtc_signaling_docker](https://github.com/because-why-not/awrtc_signaling_docker)

## Testing via Local Loopback
To run a first test, open two terminal windows and run:

In terminal 1:
```
python call_app.py -l test1234 --video --audio
```

In terminal 2:
```
python call_app.py test1234
```

The first app will now stream a dummy video feed to the second. The second will playback video and audio received.


## Testing via Browser
To stream from/to the browser, run the following in the terminal:
```
python call_app.py -l test1234 --video --audio
```

To connect to the browser open the [Browser CallApp Example](https://because-why-not.com/webrtc/callapp.html?a=test1234) and press join
or build your own via the ([awrtc_browser github](https://github.com/because-why-not/awrtc_browser)).
Note signaling server can only be changed if rebuild via github (change the URI [here](https://github.com/because-why-not/awrtc_browser/blob/master/src/apps/callapp.ts#L74)). 

## Other examples

## Testing via Cross-platform Unity Asset WebRTC Video Chat
1. Open the scene `callapp/callscene`
2. Press Start
3. Enter `test1234` into the text field
4. Press Join

The signaling server can be changed via the Unity Editor by clicking on the CallApp object and changing the signaling server URL in the inspector. 

Wait for another user to connect and then send video from a file:

```
python call_app.py -l test1234 --from-file your_video.mp4
```

Save incoming audio and video to a file (will overwrite files without warning!):

```
python call_app.py -l test1234 --to-file out_video.mp4
```

# Pitfalls
## Mac
You might need to install portaudio for the setup process to work.
This can be done via brew:
```
brew install portaudio
#then reinstall pip modules
pip install -r requirements.txt
```

## Ubuntu
Note: The example apps might stall on Ubuntu when receiving a video feed and showing it via the UI. 
This is a bug when incompatible versions of AV and OpenCV are used. See:
https://github.com/opencv/opencv/issues/21952
https://github.com/PyAV-Org/PyAV/issues/978
Outputting video to a file via --to-file works.


You might need to install portaudio for the setup process to work.
```
apt install portaudio19-dev
#then reinstall pip modules
pip install -r requirements.txt
```
