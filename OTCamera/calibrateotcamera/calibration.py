import numpy as np
import cv2 as cv
import glob
import os
import json
from hardware import camera
import config
import guiweb


K = []
D = []

fpath = "data.txt"



# saves  distortion coefficients in json-file
def dumpParams(fpath, K, D):
    # if not os.path.exists(fpath):
    #     directory = fpath.split()
    #     os.mkdir(directory)
    data = dict()
    K = K.tolist()
    D = D.tolist()
    data['K'] = K
    data['D'] = D
    to_json = json.dumps(data, indent=4)
    x = open(fpath, 'w')
    x.write(to_json)

# termination criteria
criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
# prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)

objp = np.zeros((6*7,3), np.float32)
objp[:,:2] = np.mgrid[0:7,0:6].T.reshape(-1,2)

# Arrays to store object points and image points from all the images.
objpoints = [] # 3d point in real world space
imgpoints = [] # 2d points in image plane.


images = glob.glob('*.jpg')


#for fname in images:



def show_chessboard_corners(PATH1, PATH2):
        img = cv.imread(PATH1)
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        # Find the chess board corners
        ret, corners = cv.findChessboardCorners(gray, (11,7), None)
        # If found, add object points, image points (after refining them)
        print(ret)
        if ret == True:
            objpoints.append(objp)
            corners2 = cv.cornerSubPix(gray,corners, (11,11), (-1,-1), criteria)
            imgpoints.append(corners)
            # Draw and display the corners
            cv.drawChessboardCorners(img, (11,7), corners2, ret)
            # exports picture to folder
            cv.imwrite(PATH2, img)
        #     calibratetext = "calibration worked"

        #     return calibratetext
        # else:
        #     calibratetext ="retake picture"
        #     # return calibratetext


        #     cv.imshow('img', img)
        #     cv.waitKey(3000)
        # cv.destroyAllWindows()

def get_coefficients(PATH):

    img = cv.imread(PATH)
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)


    print('camera matrix\n', mtx, '\n')
    print('distorsion matrix\n', dist, '\n')

    dumpParams(fpath, mtx, dist)


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