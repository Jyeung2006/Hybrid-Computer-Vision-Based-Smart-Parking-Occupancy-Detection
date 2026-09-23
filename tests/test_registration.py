import cv2
import numpy as np
import pytest
from parking_probe.registration import FrameRegistration
from parking_probe.sources import SourceError


def test_registration_aligns_small_drift_but_rejects_large_change():
    rng=np.random.default_rng(14)
    image=rng.integers(0,256,(360,640,3),dtype=np.uint8)
    reg=FrameRegistration(image,{'min_inliers':80,'max_displacement_pixels':35})
    drift=cv2.warpAffine(image,np.float32([[1,0,7],[0,1,-4]]),(640,360))
    aligned,info=reg.apply(drift)
    assert info['inliers']>80 and info['max_displacement_pixels']<10
    assert np.abs(aligned[20:-20,20:-20].astype(float)-image[20:-20,20:-20]).mean()<8
    with pytest.raises(SourceError):reg.apply(cv2.warpAffine(image,np.float32([[1,0,90],[0,1,0]]),(640,360)))
    with pytest.raises(SourceError):reg.apply(np.zeros_like(image))
    with pytest.raises(SourceError):reg.apply(image[:200])
