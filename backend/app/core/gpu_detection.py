from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

GPU_BACKEND_CUDA = "cuda"
GPU_BACKEND_ROCM = "rocm"
GPU_BACKEND_VULKAN = "vulkan"
GPU_BACKEND_MPS = "mps"
GPU_BACKEND_XPU = "xpu"
GPU_BACKEND_NONE = "cpu"


def _detect_backend() -> str:
    try:
        import torch
    except ImportError:
        return GPU_BACKEND_NONE

    # AMD ROCm — torch.cuda.is_available() returns True with HIP
    if getattr(torch.version, "hip", None) is not None:
        return GPU_BACKEND_ROCM

    # NVIDIA CUDA
    if torch.cuda.is_available():
        return GPU_BACKEND_CUDA

    # Intel XPU (oneAPI)
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return GPU_BACKEND_XPU

    # Apple MPS
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return GPU_BACKEND_MPS

    # Vulkan (covers AMD APUs, Intel, other Vulkan-capable GPUs)
    if (
        hasattr(torch.backends, "vulkan")
        and torch.backends.vulkan.is_available()
    ):
        return GPU_BACKEND_VULKAN

    return GPU_BACKEND_NONE


_backend: str | None = None


def detect_gpu_backend() -> str:
    global _backend
    if _backend is None:
        _backend = _detect_backend()
        logger.info("GPU backend detected: %s", _backend)
    return _backend


def gpu_device_name() -> str | None:
    import torch

    backend = detect_gpu_backend()
    try:
        if backend == GPU_BACKEND_CUDA:
            return torch.cuda.get_device_name(0)
        if backend == GPU_BACKEND_ROCM:
            name = torch.cuda.get_device_name(0)
            hip_ver = getattr(torch.version, "hip", "")
            return f"{name} (ROCm {hip_ver})" if hip_ver else name
        if backend == GPU_BACKEND_XPU:
            return "Intel XPU"
        if backend == GPU_BACKEND_MPS:
            return "Apple MPS"
        if backend == GPU_BACKEND_VULKAN:
            return "Vulkan"
    except Exception:
        logger.exception("Failed to get GPU device name")
    return None


def get_optimal_device() -> str:
    return detect_gpu_backend()


def is_gpu_available() -> bool:
    return detect_gpu_backend() != GPU_BACKEND_NONE


def is_amd_gpu() -> bool:
    return detect_gpu_backend() == GPU_BACKEND_ROCM


def gpu_backend_label() -> str:
    labels = {
        GPU_BACKEND_CUDA: "NVIDIA CUDA",
        GPU_BACKEND_ROCM: "AMD ROCm",
        GPU_BACKEND_VULKAN: "Vulkan",
        GPU_BACKEND_MPS: "Apple MPS",
        GPU_BACKEND_XPU: "Intel XPU",
        GPU_BACKEND_NONE: "CPU",
    }
    return labels.get(detect_gpu_backend(), "CPU")
