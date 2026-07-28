# 2. Vulkan over ROCm for Inference

Date: 2026-07-25

## Status
Accepted

## Context
The target hardware for local AI inference includes an AMD Radeon RX 580 GPU (Polaris architecture). AMD's primary compute stack, ROCm, officially dropped support for Polaris/GCN4 hardware, making ROCm installation brittle or completely unsupported on modern operating systems.

## Decision
We will standardize all local LLM and transcription inference (`llama.cpp`, `whisper.cpp`) using the **Vulkan** backend instead of ROCm.

## Consequences
- **Positive:** Guaranteed hardware compatibility with the RX 580 without fighting deprecated ROCm drivers. Vulkan works natively on Windows and Linux.
- **Negative:** Vulkan backends can sometimes lag slightly in performance optimization compared to native CUDA/ROCm, but it provides the necessary stability and VRAM offloading required for the 16GB RAM constraints of the host system.
