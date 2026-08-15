# YTAuto Operator Control Center (Frontend)

Modular React 19 Single Page Application (SPA) with TypeScript and Vite. Provides real-time hardware telemetry, pipeline job inspection, Quality Gate video review workbench, Reddit story ingestion, background asset management, and system configuration.

---

## Key Features

- **Hash-Based URL Routing**: Fully persistent navigation across page refreshes (`#/overview`, `#/stories`, `#/jobs`, `#/review`, `#/assets`, `#/backgrounds`, `#/sources`, `#/rights`, `#/settings`).
- **Real-Time Hardware Telemetry**: Live CPU utilization %, System RAM headroom (in GB), GPU dedicated VRAM (AMD Radeon RX 580 via Windows Performance Counters), and storage footprint gauges.
- **Coexistence Governor**: Real-time evaluation of host memory headroom (`optimal`, `contended`, `critical`) to ensure safe multi-workload coexistence (e.g. OpenWorker).
- **Stage Execution Profiler**: Live latency benchmarks, peak RAM/VRAM deltas, and LLM token generation speed.
- **Quality Gate Workbench**: Keyboard-driven reviewer (`Space` for play/pause, `A` for approve, `R` for reject, `ArrowRight`/`ArrowLeft` for card navigation) with virality score breakdown (Hook Strength, Curiosity Gap, Emotional Intensity, Story Compleherence).
- **Curated Reddit Story Studio**: Ingest text narratives with auto-formatting cleaner, narrator voice profile selector (Ryan High, Amy Medium, Lessac High), duration estimator (~140 wpm), and vertical 9:16 Shorts rendering.
- **Sticky Viewport Sidebar**: Fixed viewport sidebar with independent scrolling and custom slim glass scrollbars.
- **Storage Lifecycle Controls**: One-click **"🧹 Flush Used Raw Sources"** and **"🗓️ Purge 7-Day Old Assets"** (with background video protection).

---

## Development & Build

```bash
# Install dependencies
npm install

# Run development server with Hot Module Replacement
npm run dev

# Build production bundle
npm run build
```
