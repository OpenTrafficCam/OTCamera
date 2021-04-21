import glob
import json
import os
from datetime import date, datetime
from pathlib import Path
from time import strftime

import cv2 as cv
import numpy as np

import config

# matrix, distcoef, error

K = []
D = []
E = []


# termination criteria
criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)


# Arrays to store object points and image points from all the images.
objpoints = []  # 3d point in real world space
imgpoints = []  # 2d points in image plane.


#images = glob.glob('*.jpg')

hostname = config.PREFIX


def calibrationfilepath():

    # watch out to have the right systemtime
    curr_date = datetime.now().strftime("date_%Y_%m_%d time_%H%M_Uhr")

    resolution = "RES"+str(config.RESOLUTION)

    fpath = config.PARAMETERPATH.format(curr_date, resolution, hostname)

    print(fpath)

    return fpath, curr_date


# saves  distortion coefficients in json-file
def dumpParams(fpath, curr_date, K, D, E):

    # TODO dump parameter in folder created

    data = dict()

    K = K.tolist()

    D = D.tolist()
    data["INFORMATION"] = [curr_date, hostname, config.RESOLUTION]
    data['K'] = K
    data['D'] = D
    data['REPROJECTION ERROR'] = E
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

    # 7 und 11 sind die reihen und spalten des Schachbrettes. Stimmen die nicht überein werden keine Parameter berechnet!!!
    objp = np.zeros((chessboardrows*chessboardcolumns, 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboardcolumns,
                           0:chessboardrows].T.reshape(-1, 2)

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

    print(mtx, dist, ret)

    print(fpath)

    # store parameter in a dictionary
    dumpParams(fpath, curr_date, mtx, dist, ret)

    return ret
