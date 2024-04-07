import cv2
import asyncio
#workaround for conflict between cv2 and av used by aiortc
#creating a window will stall after both cv2 and airortc are included
window_title = "Video Feed"
cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)

from aiortc import VideoStreamTrack
from aiortc.contrib.media import MediaPlayer

class CameraStreamTrack(VideoStreamTrack):
    """
    A video stream track that captures video from the camera.
    """
    def __init__(self):
        super().__init__() 
        
        #self.player = MediaPlayer('/dev/video0', format='v4l2', options={'video_size': '640x480'})
        self.player = MediaPlayer('video.mp4')

    async def recv(self):
        frame = await self.player.video.recv()
        return frame


#on newer ubuntu versions it might need this?
#sudo apt install qtwayland5
async def display_video_track(track: VideoStreamTrack):
    """
    Display video frames from an aiortc VideoStreamTrack using OpenCV.
    
    :param track: The aiortc VideoStreamTrack to display.
    """
    
    try:
        while True:
            frame = await track.recv()
            image = frame.to_ndarray(format="bgr24")  # Convert frame to an ndarray in BGR format.

            cv2.imshow(window_title, image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cv2.destroyAllWindows()

#python3 test_video.py
if __name__ == "__main__":
    print("Start")
    camera_track = CameraStreamTrack()
    asyncio.run(display_video_track(camera_track))
