"""
Small demo program of detections
If someone want to just use the same detections
"""

import pytest
import cv2
import numpy as np
import sys
try:
    sys.path.insert(0,'../..')
    from FloorplanToBlenderLib import * # floorplan to blender lib
except ImportError:
    from FloorplanToBlenderLib import * # floorplan to blender lib

from subprocess import check_output
import os
import imutils


def test(path):
    '''
    Receive image, convert
    This function test functions used to create floor and walls
    '''
    # Read floorplan image
    img = cv2.imread(path)
    image = img
    # grayscale image
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

    # Resulting image
    height, width, channels = img.shape
    blank_image = np.zeros((height,width,3), np.uint8) # output image same size as original

    # create wall image (filter out small objects from image)
    wall_img = detect.wall_filter(gray)
    wall_temp = wall_img
    '''
    Detect Wall
    '''
    # detect walls
    boxes, img = detect.detectPreciseBoxes(wall_img, blank_image)

    '''
    Detect Floor
    '''
    # detect outer Contours (simple floor or roof solution)
    contour, img = detect.detectOuterContours(gray, blank_image, color=(255,0,0))

    # grayscale
    gray = ~wall_temp

    '''
    Detect rooms
    '''
    rooms, colored_rooms = detect.find_rooms(gray.copy())
    gray_rooms =  cv2.cvtColor(colored_rooms,cv2.COLOR_BGR2GRAY)
    boxes, blank_image = detect.detectPreciseBoxes(gray_rooms, blank_image, color=(0,100,200))

    '''
    Detect details
    '''
    doors, colored_doors = detect.find_details(gray.copy())
    gray_details = cv2.cvtColor(colored_doors,cv2.COLOR_BGR2GRAY)
    boxes, blank_image = detect.detectPreciseBoxes(gray_details, blank_image, color=(0,200,100))

    cv2.imshow('detection', blank_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


test("../example.png")