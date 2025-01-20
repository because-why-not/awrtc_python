# Quick example for testing if the current environment is
# affected by the OpenCV/AV bug that causes stalling

import cv2
import av

if __name__ == "__main__":
    print("If the app stalls below, you are affected by the bug.")
    cv2.namedWindow("test", cv2.WINDOW_NORMAL)
    print("Did not stall. All good!")