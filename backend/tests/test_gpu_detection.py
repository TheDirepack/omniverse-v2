from unittest.mock import patch, MagicMock

import pytest

from app.core.gpu_detection import (
    detect_gpu_backend,
    gpu_device_name,
    get_optimal_device,
    gpu_backend_label,
    is_gpu_available,
    is_amd_gpu,
    GPU_BACKEND_CUDA,
    GPU_BACKEND_ROCM,
    GPU_BACKEND_VULKAN,
    GPU_BACKEND_MPS,
    GPU_BACKEND_XPU,
    GPU_BACKEND_NONE,
)


@pytest.fixture(autouse=True)
def reset_cache():
    import app.core.gpu_detection as gd
    gd._backend = None
    yield
    gd._backend = None


def _mock_torch(attrs: dict, version_hip: str | None = None):
    fake_torch = MagicMock()
    fake_torch.version = MagicMock()
    fake_torch.version.hip = version_hip
    fake_torch.backends = MagicMock()
    for key, val in attrs.items():
        parts = key.split(".")
        target = fake_torch
        for p in parts[:-1]:
            target = getattr(target, p)
        setattr(target, parts[-1], val)
    return fake_torch


class TestDetectGpuBackend:
    def test_cuda(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True})
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert detect_gpu_backend() == GPU_BACKEND_CUDA

    def test_rocm(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True})
        fake_torch.version.hip = "6.0"
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert detect_gpu_backend() == GPU_BACKEND_ROCM

    def test_vulkan(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: False,
            "backends.mps.is_available": lambda: False,
            "backends.vulkan.is_available": lambda: True,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert detect_gpu_backend() == GPU_BACKEND_VULKAN

    def test_mps(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: False,
            "backends.mps.is_available": lambda: True,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert detect_gpu_backend() == GPU_BACKEND_MPS

    def test_xpu(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: True,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert detect_gpu_backend() == GPU_BACKEND_XPU

    def test_cpu_fallback(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: False,
            "backends.mps.is_available": lambda: False,
            "backends.vulkan.is_available": lambda: False,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert detect_gpu_backend() == GPU_BACKEND_NONE

    def test_no_torch(self):
        with patch.dict("sys.modules", {"torch": None}):
            import importlib
            import app.core.gpu_detection as gd
            importlib.reload(gd)
            assert gd.detect_gpu_backend() == GPU_BACKEND_NONE


class TestGpuHelpers:
    def test_is_gpu_available_true(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True})
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert is_gpu_available() is True

    def test_is_gpu_available_false(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: False,
            "backends.mps.is_available": lambda: False,
            "backends.vulkan.is_available": lambda: False,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert is_gpu_available() is False

    def test_is_amd_gpu_rocm(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True})
        fake_torch.version.hip = "6.0"
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert is_amd_gpu() is True

    def test_is_amd_gpu_nvidia(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True})
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert is_amd_gpu() is False

    def test_gpu_device_name_cuda(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True, "cuda.get_device_name": lambda x: "RTX 4090"})
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert gpu_device_name() == "RTX 4090"

    def test_gpu_device_name_rocm(self):
        fake_torch = _mock_torch({"cuda.is_available": lambda: True, "cuda.get_device_name": lambda x: "AMD Radeon RX 7900 XTX"})
        fake_torch.version.hip = "6.0"
        with patch.dict("sys.modules", {"torch": fake_torch}):
            name = gpu_device_name()
            assert "AMD Radeon" in name
            assert "ROCm" in name

    def test_gpu_device_name_mps(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: False,
            "backends.mps.is_available": lambda: True,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert gpu_device_name() == "Apple MPS"

    def test_gpu_device_name_no_gpu(self):
        fake_torch = _mock_torch({
            "cuda.is_available": lambda: False,
            "xpu.is_available": lambda: False,
            "backends.mps.is_available": lambda: False,
            "backends.vulkan.is_available": lambda: False,
        })
        fake_torch.version.hip = None
        with patch.dict("sys.modules", {"torch": fake_torch}):
            assert gpu_device_name() is None

    def test_labels(self):
        assert gpu_backend_label() in (
            "NVIDIA CUDA", "AMD ROCm", "Vulkan", "Apple MPS", "Intel XPU", "CPU"
        )

    def test_get_optimal_device_matches_detect(self):
        assert get_optimal_device() == detect_gpu_backend()
