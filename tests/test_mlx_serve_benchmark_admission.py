import io
from types import SimpleNamespace

import pytest

from scripts.run_frozen_product_reader import require_idle_local_reader


@pytest.mark.parametrize('running,waiting', [(0, 0), (1, 0), (0, 1)])
def test_mlx_serve_admission(monkeypatch, running, waiting):
    def open_metrics(url, timeout):
        assert url == 'http://127.0.0.1:11234/metrics'
        return io.BytesIO((f'vllm:num_requests_running {running}\n'
                           f'vllm:num_requests_waiting {waiting}\n').encode())
    monkeypatch.setattr('urllib.request.build_opener',
                        lambda *args: SimpleNamespace(open=open_metrics))
    if running or waiting:
        with pytest.raises(RuntimeError):
            require_idle_local_reader('mlx-serve')
    else:
        require_idle_local_reader('mlx-serve')


def test_missing_metrics_does_not_admit(monkeypatch):
    monkeypatch.setattr('urllib.request.build_opener',
                        lambda *args: SimpleNamespace(open=lambda *a, **k: io.BytesIO(b'')))
    with pytest.raises(KeyError):
        require_idle_local_reader('mlx-serve')
