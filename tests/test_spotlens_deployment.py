import base64
import importlib.util
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/spotlens/serve.py'
spec = importlib.util.spec_from_file_location('spotlens_deployment', MODULE)
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


@pytest.fixture
def package(tmp_path):
    (tmp_path / 'public').mkdir()
    (tmp_path / 'public/index.html').write_text('<html>Spotlens</html>')
    (tmp_path / 'presets').mkdir()
    for name in ('chad-camera-1-expanded', 'overhead-all-bays'):
        (tmp_path / 'presets' / (name + '.json')).write_text(json.dumps({'slots': [{'bay_id': name}]}))
    return tmp_path


def request(server, path='/', method='GET', origin=None, auth=None, host='parking.example.com'):
    headers = {'Host': host, 'X-Parking-Client': 'web'}
    if origin:
        headers['Origin'] = origin
    if auth:
        headers['Authorization'] = auth
    data = b'{"source_id":"chad-1"}' if method == 'POST' else None
    try:
        with urlopen(Request(f'http://127.0.0.1:{server.server_port}' + path,
            headers=headers, data=data, method=method)) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def serve(root, **kwargs):
    server = deployment.make_server(port=0, root=root,
        origins={'https://parking.example.com'}, **kwargs)
    server.replay_job.start = lambda source: False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def close(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_host_and_https_origin_contract(package):
    server, thread = serve(package)
    try:
        assert request(server)[0] == 200
        assert request(server, host='untrusted.example')[0] == 403
        assert request(server, '/api/replay/start', 'POST', 'https://parking.example.com')[0] == 409
        assert request(server, '/api/replay/start', 'POST', 'https://untrusted.example')[0] == 403
        assert request(server, '/api/replay/start', 'POST', 'http://parking.example.com')[0] == 403
        assert request(server, '/serve.py')[0] == 404
        assert request(server, '/data/chad/1_029_0.mp4')[0] == 404
    finally:
        close(server, thread)


def test_optional_basic_authentication(package):
    server, thread = serve(package, username='demo', password='test-pass')
    try:
        assert request(server)[0] == 401
        assert request(server, auth='Basic wrong')[0] == 401
        token = base64.b64encode(b'demo:test-pass').decode()
        assert request(server, auth='Basic ' + token)[0] == 200
    finally:
        close(server, thread)


def test_origin_and_credentials_validation(package):
    assert deployment.parse_origins('https://parking.example.com/,http://localhost:8765') == {
        'https://parking.example.com', 'http://localhost:8765'}
    for value in ('*', 'https://parking.example.com/path', 'https://user:password@example.com'):
        with pytest.raises(ValueError):
            deployment.parse_origins(value)
    with pytest.raises(ValueError):
        deployment.make_server(port=0, root=package, username='demo')
