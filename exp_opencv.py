import numpy as np
import cv2

# Create a black image of 512x512 pixels, 3 channels (RGB), and 8 bits per channel
empty_image = np.zeros((512, 512, 3), np.uint8)

# Create a named window
cv2.namedWindow('Test Window', cv2.WINDOW_NORMAL)

# Display the empty (black) image in the named window
cv2.imshow('Test Window', empty_image)

# Wait for a key press before closing the window
while True:
    cv2.waitKey(1)

# Destroy all windows created by your script
cv2.destroyAllWindows()
