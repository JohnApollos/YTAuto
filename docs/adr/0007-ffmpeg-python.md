# 7. Standard FFmpeg over MoviePy for Rendering

Date: 2026-07-28

## Status
Accepted

## Context
In Phase 3, we needed a rendering engine capable of compositing vertical 9:16 video from 16:9 source footage. This involved cropping, scaling, heavy blurring (for backgrounds), overlaying foreground footage, and burning in subtitles (with custom fonts/styles). 
The choice was between `MoviePy` (a higher-level Pythonic wrapper for video editing) and raw `FFmpeg` filtergraphs (via `ffmpeg-python`).

## Decision
We chose to rely exclusively on `FFmpeg` filtergraphs via the `ffmpeg-python` wrapper.

## Consequences
- **Positive**: FFmpeg is orders of magnitude faster for rendering intensive effects like boxblurs and scaling compared to MoviePy, which often decodes/encodes frames individually in Python. Furthermore, FFmpeg's `subtitles` filter is significantly more robust and reliable than MoviePy's dependency on ImageMagick for text overlay generation.
- **Negative**: The syntax for constructing `FFmpeg` filtergraphs is notoriously difficult to read and debug. To mitigate this, we encapsulated the filtergraph construction inside the `FFmpegCompositor` class in `autonomous_media/rendering/compositor.py` so it never leaks into the core Worker logic.
