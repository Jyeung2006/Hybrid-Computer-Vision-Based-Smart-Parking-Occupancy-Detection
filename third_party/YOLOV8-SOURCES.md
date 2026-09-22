# YOLOv8s model provenance and conversion

Retrieved and converted 19 September 2026. These sources supply model weights and architecture; their reported benchmark metrics are not results measured by this project.

| Profile | Checkpoint and pinned provenance | SHA-256 |
| --- | --- | --- |
| COCO | [Ultralytics assets v8.3.0 / yolov8s.pt](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt), 22,588,772 bytes | `1f47a78bf100391c2a140b7ac73a1caae18c32779be7d310658112f7ac9aa78a` |
| Aerial | [dronefreak/visdrone-yolov8s model card](https://huggingface.co/dronefreak/visdrone-yolov8s), revision `4475b4d86d5f4b120806d1b953be15cedaac9285`, `best.pt`, 22,546,666 bytes | `9b9911be383dabfd3376c5b882dc520d84faaa6282271dce75830555268b35bc` |

Pinned aerial download: [best.pt](https://huggingface.co/dronefreak/visdrone-yolov8s/resolve/4475b4d86d5f4b120806d1b953be15cedaac9285/best.pt). Its model card labels the model AGPL-3.0 and describes fine-tuning YOLOv8s on VisDrone. Its output has 11 classes. This project accepts IDs 3 car, 4 van, 5 truck, 8 bus and 9 motor. COCO accepts IDs 2 car, 3 motorcycle, 5 bus and 7 truck among 80 classes.

Ultralytics publishes [YOLOv8 documentation](https://docs.ultralytics.com/models/yolov8/), [export documentation](https://docs.ultralytics.com/modes/export/) and [licensing information](https://www.ultralytics.com/license). A copy of its v8.3.203 AGPL-3.0 license is [YOLOV8-AGPL-3.0.txt](YOLOV8-AGPL-3.0.txt). The architecture/export implementation used is [Ultralytics v8.3.203](https://github.com/ultralytics/ultralytics/tree/v8.3.203). Runtime uses [OpenCV's DNN YOLO support](https://docs.opencv.org/4.x/da/d9d/tutorial_dnn_yolo.html) with project-owned preprocessing, output parsing and polygon association.

## Rebuild the bundled runtime assets

Normal Run does **not** need this. A reproducible conversion script is [scripts/export_yolov8_models.py](../scripts/export_yolov8_models.py). It verifies pinned checkpoint hashes, downloads with bounded time/size limits if needed, and rejects unknown checkpoint class requirements. Checkpoints were read using PyTorch `weights_only=True` and an explicit allowlist of known installed Torch/Ultralytics neural-layer classes. No repository-supplied Python code was executed. ONNX runtime loading does not deserialize Python checkpoints.

Tested conversion environment: Python 3.12.14, torch 2.7.1+cpu, torchvision 0.22.1+cpu, ultralytics 8.3.203, onnx 1.19.0. Full installed snapshot: [requirements-yolo-export-tested.txt](../requirements-yolo-export-tested.txt). Rebuilding uses static FP32 640×640, batch one, ONNX opset 12, no graph simplification and no embedded NMS.

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e ".[yolo-export]"
.\.venv\Scripts\python.exe scripts/export_yolov8_models.py
.\.venv\Scripts\python.exe checks/check_interface.py
```

The export script was executed successfully for both profiles. ONNX metadata can change file digests on rebuild, so the script updates the derived ONNX hashes in [yolov8s-manifest.json](../assets/models/yolov8s-manifest.json), preserving pinned checkpoint hashes. Exported sizes are 44,842,278 and 44,734,231 bytes. Always run inference/integration checks after rebuilding.

Export settings are directed to `data/models/yolo-settings/`. Initial conversion experiments also created default Ultralytics settings in the workspace and the current user's AppData folder; no personal configuration was removed. No Windows security settings were changed. Only local model conversion/inference was performed; no account or external inference service was used.
