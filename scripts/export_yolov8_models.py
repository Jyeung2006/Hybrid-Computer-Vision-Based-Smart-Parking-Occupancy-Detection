"""Rebuild bundled ONNX assets from pinned checkpoints; not needed for normal Run.

Install CPU torch/torchvision first, then this project's [yolo-export] extras.
Only installed known neural-network classes are allowlisted for weights-only load.
"""
from pathlib import Path
import hashlib
import importlib
import json
import os
import time

ROOT=Path(__file__).resolve().parents[1]
settings=ROOT/'data/models/yolo-settings'
settings.mkdir(parents=True,exist_ok=True)
os.environ['YOLO_CONFIG_DIR']=str(settings)
os.environ['YOLO_AUTOINSTALL']='false'


def main():
    import requests
    import torch
    import ultralytics
    from ultralytics import YOLO
    import onnx
    out=ROOT/'assets/models'
    manifest=json.loads((out/'yolov8s-manifest.json').read_text())
    if ultralytics.__version__!='8.3.203' or onnx.__version__!='1.19.0':
        raise RuntimeError('Use the documented pinned export versions.')
    modules={'ultralytics.nn.modules','ultralytics.nn.modules.conv','ultralytics.nn.modules.block',
             'ultralytics.nn.modules.head','ultralytics.nn.tasks','torch.nn.modules.conv',
             'torch.nn.modules.batchnorm','torch.nn.modules.container','torch.nn.modules.linear',
             'torch.nn.modules.pooling','torch.nn.modules.upsampling','torch.nn.modules.activation'}
    names={'Conv','Conv2d','Concat','Bottleneck','Detect','DFL','DetectionModel','SPPF','C2f',
           'BatchNorm2d','Sequential','ModuleList','Identity','MaxPool2d','Upsample','SiLU'}
    for key,info in manifest['profiles'].items():
        source=info['source'];directory=ROOT/'data/models'/('yolov8s' if key=='coco' else 'yolov8s-visdrone')
        directory.mkdir(parents=True,exist_ok=True)
        checkpoint=directory/('yolov8s.pt' if key=='coco' else 'best.pt')
        if not checkpoint.exists() or hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=source['sha256']:
            partial=checkpoint.with_suffix('.part');count=0;digest=hashlib.sha256();started=time.monotonic()
            try:
                with requests.get(source.get('source_url',source.get('url')),stream=True,timeout=(5,20)) as response:
                    response.raise_for_status()
                    with partial.open('wb') as handle:
                        for block in response.iter_content(262144):
                            count+=len(block)
                            if count>source['bytes'] or time.monotonic()-started>120:
                                raise RuntimeError('Checkpoint download limit exceeded.')
                            digest.update(block);handle.write(block)
                if count!=source['bytes'] or digest.hexdigest()!=source['sha256']:
                    raise RuntimeError('Checkpoint integrity check failed.')
                partial.replace(checkpoint)
            finally:partial.unlink(missing_ok=True)
        allowed=[]
        for full in torch.serialization.get_unsafe_globals_in_checkpoint(checkpoint):
            module,name=full.rsplit('.',1)
            if module not in modules or name not in names:
                raise RuntimeError(f'Checkpoint requires an unapproved class: {full}')
            allowed.append((getattr(importlib.import_module(module),name),full))
        with torch.serialization.safe_globals(allowed):
            data=torch.load(checkpoint,map_location='cpu',weights_only=True)
        model=YOLO('yolov8s.yaml')
        model.model=(data.get('ema') or data['model']).float()
        model.model.task='detect';model.task='detect';model.model.pt_path=str(checkpoint)
        exported=Path(model.export(format='onnx',imgsz=640,opset=12,simplify=False,dynamic=False,nms=False,device='cpu'))
        # Timestamps/metadata can change a byte digest on rebuild. Record this
        # newly derived artifact, preserving pinned input-checkpoint provenance.
        target=out/info['file'];target.write_bytes(exported.read_bytes())
        info.update(size=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (out/'yolov8s-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Export complete. Run the detector/integration checks before adopting rebuilt artifacts.')


if __name__=='__main__':main()
