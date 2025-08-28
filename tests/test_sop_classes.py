import os

import numpy as np
import vreg
from dbdicom.sop_classes import enhanced_mr_image




def test_enhanced_mri_volume():
    return
    dims = [
        'MRTimingAndRelatedParametersSequence/FlipAngle', 
        'MRTimingAndRelatedParametersSequence/RepetitionTime', 
        'MRTimingAndRelatedParametersSequence/EchoTime',
    ]
    nFA, nTR, nTE = 3, 5, 4
    values = np.random.rand(128, 192, 15, nFA, nTR, nTE) * 100
    vol = vreg.volume(values, orient='coronal', dims=dims, spacing=[0.5, 0.5, 1.5])

    ds = enhanced_mr_image.from_volume(vol)

    path = os.path.join(os.getcwd(), 'tmp')
    os.makedirs(path, exist_ok=True)
    file = os.path.join(path, 'test_enhanced_mri.dcm')
    ds.save_as(file, enforce_file_format=True)





if __name__ == '__main__':
    test_enhanced_mri_volume()