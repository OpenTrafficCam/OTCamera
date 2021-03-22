from time import strftime
import numpy as np
import cv2 as cv
import glob
import os
import json
from datetime import datetime, date
import config


K = []
D = []


# termination criteria
criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)


# 7 und 11 sind die reihen und spalten des Schachbrettes. Stimmen die nicht überein werden keine Parameter berechnet!!!

# TO DO 9,6 REPRESENT ROWS AND COLUMNS!!! PLS CHANGE
objp = np.zeros((11*7, 3), np.float32)
objp[:, :2] = np.mgrid[0:7, 0:11].T.reshape(-1, 2) 

# Arrays to store object points and image points from all the images.
objpoints = []  # 3d point in real world space
imgpoints = []  # 2d points in image plane.

# change to pathlib
images = glob.glob('*.jpg')

hostname = config.PREFIX


def calibrationfilepath():

    # watch out to have the right systemtime
    curr_date = datetime.now().strftime("date_%Y_%m.%d time_%H%MUhr")

    resolution = "RES"+str(config.RESOLUTION)

    fpath = config.PARAMETERPATH.format(curr_date, resolution, hostname)

    return fpath, curr_date


# saves  distortion coefficients in json-file
def dumpParams(fpath, curr_date, K, D):

    print(fpath)
    data = dict()
    K = K.tolist()
    D = D.tolist()

    data["INFORMATION"] = [curr_date, hostname, config.RESOLUTION]
    data['K'] = K
    data['D'] = D
    to_json = json.dumps(data, indent=4)
    x = open(fpath, 'w')
    x.write(to_json)


def show_chessboard_corners(inputpath, outputpath, chessboardrows, chessboardcolumns, squaresize):
    img = cv.imread(inputpath)
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    # Find the chess board corners
    ret, corners = cv.findChessboardCorners(
        gray, (chessboardcolumns, chessboardrows), None)
    # If found, add object points, image points (after refining them)
    print(ret)
    if ret == True:
        objpoints.append(objp*squaresize)
        corners2 = cv.cornerSubPix(
            gray, corners, (11, 11), (-1, -1), criteria)
        imgpoints.append(corners)
        # Draw and display the corners
        cv.drawChessboardCorners(
            img, (chessboardcolumns, chessboardrows), corners2, ret)
        # exports picture to folder
        cv.imwrite(outputpath, img)


def get_coefficients(FIRSTIMAGEPATH):

    img = cv.imread(FIRSTIMAGEPATH)
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    fpath, curr_date = calibrationfilepath()

    try:
        ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(
            objpoints, imgpoints, gray.shape[::-1], None, None)
    except:
        print("not working")
    print('camera matrix\n', mtx, '\n')
    print('distorsion matrix\n', dist, '\n')

    dumpParams(fpath, curr_date, mtx, dist)


# #shows calibrated picture
# for fname in images:
#     img = cv.imread(fname)
#     h,  w = img.shape[:2]
#     newcameramtx, roi = cv.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))

#     #undistort
#     dst = cv.undistort(img, mtx, dist, None, newcameramtx)

#     #crop the image
#     x, y, w, h = roi
#     dst = dst[y:y+h, x:x+w]

#     #save calibrated picture
#     cv.imwrite('calibresult.png', dst)
#     cv.imshow('img', img)
#     cv.waitKey(10000)
