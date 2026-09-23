# MobileNet-SSD model attribution

The user approved a pretrained vehicle detector to supplement Reference and MOG2 on 19 September 2026. This project uses OpenCV DNN to load the Caffe model distributed by [chuanqi305/MobileNet-SSD](https://github.com/chuanqi305/MobileNet-SSD). No YOLO, external detection code, pickle annotations or additional Python package is used.

Pinned revision: `bb17b6c3eef36d80be441ae8e5339be66e8e3b7a`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| deploy.prototxt | 44,667 | 2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608 |
| mobilenet_iter_73000.caffemodel | 23,306,119 | 52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7 |

The repository supplies an MIT license, copied unchanged to [MOBILENET-SSD-LICENSE.txt](MOBILENET-SSD-LICENSE.txt). That repository license is not a new license grant for the CHAD videos or underlying training datasets. The model source files and metadata are cached under `data/models/mobilenet-ssd/`; the downloader in `src/parking_probe/vehicle.py` verifies pinned sizes/hashes and bounds time/bytes before atomic replacement.

CPU inference uses a BGR 300x300 blob, scale 1/127.5 and mean 127.5. Full-frame inference plus four overlapping crops improves small-vehicle visibility. Kept classes are car, bus and motorbike. Model scores are not calibrated probabilities that a parking bay is occupied. See [CAMERA_MAPPING.md](../CAMERA_MAPPING.md) for association and final-state rules. OpenCV API reference: [DNN module](https://docs.opencv.org/4.x/d6/d0f/group__dnn.html).
