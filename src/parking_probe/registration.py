"""Guarded registration for the reviewed, gently drifting overhead recording."""
import math
import cv2
import numpy as np
from .sources import SourceError


class FrameRegistration:
    def __init__(self, setup, settings):
        self.setup = setup
        self.settings = settings
        self.orb = cv2.ORB_create(nfeatures=5000, edgeThreshold=15)
        self.keys, self.descriptors = self.orb.detectAndCompute(cv2.cvtColor(setup, cv2.COLOR_BGR2GRAY), None)

    def apply(self, image):
        if image.shape != self.setup.shape:
            raise SourceError('resolution_changed')
        keys, descriptors = self.orb.detectAndCompute(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), None)
        if descriptors is None or self.descriptors is None:
            raise SourceError('registration_insufficient_features')
        pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors, self.descriptors, k=2)
        good = [a[0] for a in pairs if len(a)==2 and a[0].distance < .7*a[1].distance]
        minimum = self.settings.get('min_inliers',80)
        if len(good) < minimum:
            raise SourceError('registration_insufficient_matches')
        a = np.float32([keys[m.queryIdx].pt for m in good])
        b = np.float32([self.keys[m.trainIdx].pt for m in good])
        matrix, mask = cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,
            ransacReprojThreshold=self.settings.get('ransac_reprojection_pixels',3))
        if matrix is None or not np.isfinite(matrix).all() or mask is None:
            raise SourceError('registration_failed')
        selected = mask.ravel()!=0
        fraction = float(selected.mean())
        h,w = image.shape[:2]
        corners = np.float32([[0,0],[w-1,0],[0,h-1],[w-1,h-1]])
        delta = float(np.linalg.norm(cv2.transform(corners[None],matrix)[0]-corners,axis=1).max())
        scale = math.hypot(matrix[0,0],matrix[1,0])
        angle = abs(math.degrees(math.atan2(matrix[1,0],matrix[0,0])))
        span = np.ptp(a[selected],axis=0) if selected.any() else np.zeros(2)
        error = float(np.median(np.linalg.norm(cv2.transform(a[None],matrix)[0]-b,axis=1)[selected])) if selected.any() else float('inf')
        if (selected.sum() < minimum or fraction < self.settings.get('min_inlier_fraction',.6)
                or span[0] < .5*w or span[1] < .5*h or error > 1.5
                or delta > self.settings.get('max_displacement_pixels',35)
                or abs(scale-1) > self.settings.get('max_scale_change',.03)
                or angle > self.settings.get('max_rotation_degrees',2)):
            raise SourceError('registration_outside_reviewed_limits')
        valid = cv2.warpAffine(np.full((h,w),255,np.uint8),matrix,(w,h),flags=cv2.INTER_NEAREST)
        self.valid_mask = valid
        return cv2.warpAffine(image,matrix,(w,h)), {'method':'orb_ransac_partial_affine_v1',
            'source_to_setup':matrix.tolist(),'inliers':int(selected.sum()),'inlier_fraction':fraction,
            'median_error_pixels':error,'max_displacement_pixels':delta,'scale':scale}
