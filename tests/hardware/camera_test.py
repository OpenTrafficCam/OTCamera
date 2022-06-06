import OTCamera.hardware.camera as camera


def test_init_camera_same_instance():
    cam_1 = camera.Camera()
    cam_2 = camera.Camera()
    assert cam_1 == cam_2
