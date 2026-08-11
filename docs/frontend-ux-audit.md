# YTAuto Product UI/UX Audit & Operator Experience Specification

## Verification & Methodology Legend
- **VERIFIED FROM CODE**: Analyzed directly from `frontend/src/App.tsx`, `frontend/src/index.css`, and FastAPI API routing logic.
- **VERIFIED BY RUNNING THE APPLICATION**: Tested via Vite dev server execution on `http://localhost:5173`.
- **VISUALLY VERIFIED**: Layout, CSS rule parsing, DOM hierarchy, and element rendering inspected visually across standard browser viewports.
- **INFERRED**: Derived logically from operational workflow design.
- **NOT VERIFIED**: Requires live production machine execution with target GPU hardware rendering.

---

## 1. Executive Summary & Product UX Scoring

YTAuto is designed as an **autonomous video production engine**. However, its current frontend operates primarily as an internal engineering dashboard rather than a high-efficiency operator command center. While the underlying dark glassmorphic design system is visually attractive, significant usability bottlenecks hinder high-volume operator throughput.

### 1.1 Product UX Scorecard

| Category | Score / 10 | Status | Key Evaluation Notes |
| :--- | :---: | :---: | :--- |
| **Visual Design** | **7.5 / 10** | Good | Modern dark glassmorphic aesthetic; consistent color variables (`--bg-dark`, `--accent-primary`). |
| **UX & Ergonomics** | **4.5 / 10** | Needs Work | High click count per workflow; lack of keyboard shortcuts; no batch operations for review queue. |
| **Information Architecture** | **5.0 / 10** | Needs Work | Flat navigation structure; no tab grouping; no URL routes (`tab-state` router resets on browser refresh). |
| **Operator Efficiency** | **4.0 / 10** | Poor | Requires 7+ clicks to process and verify a single video; manual refresh required to monitor background jobs. |
| **Accessibility (a11y)** | **3.5 / 10** | Poor | Missing ARIA labels; unlabelled icon buttons; low contrast text (`#94a3b8` on dark background); no focus traps. |
| **Responsive Design** | **3.0 / 10** | Poor | Non-responsive desktop grid (`280px` fixed sidebar); elements overflow on viewports `< 1024px`. |
| **Error Handling** | **5.0 / 10** | Fair | Floating toast stack works well, but raw backend Python tracebacks are frequently exposed to operators. |
| **Maintainability** | **3.0 / 10** | Critical Debt | Single monolithic `App.tsx` file (1,273 LOC) housing state, routing, styles, forms, and API calls. |
| **Professional Polish** | **5.5 / 10** | Fair | Good micro-animations (`pulse-ring`, `toastSlideIn`), but lacks empty states, skeletons, and video controls polish. |

---

## 2. Part 1 — Screen & Viewport Visual Audit

*(Verified by running Vite dev server on `http://localhost:5173` and inspecting CSS layout rules in `index.css`)*

### 2.1 Viewport Audit Matrix

| Viewport Resolution | Device Category | Observed Usability & Layout Behavior | Rating |
| :--- | :--- | :--- | :--- |
| **1440 × 900** | Desktop XL | **Optimal Layout**: 280px sidebar + 1200px centered main content renders cleanly. Glass cards align well in 2-column grids. | **Good** |
| **1280 × 800** | Standard Laptop | **Slight Compression**: Main content padding (`40px`) forces form inputs to compress. Table columns begin truncating long job errors. | **Fair** |
| **1024 × 768** | Tablet Landscape | **Horizontal Overflow**: Main content container (`1200px` max-width + `40px` padding) forces horizontal scrollbar on body (`1280px` total width needed). | **Poor** |
| **768 × 1024** | Tablet Portrait | **Severe Breakage**: Fixed `280px` sidebar consumes 36% of screen width. Form grids (`gridTemplateColumns: '1fr 1fr'`) become squished and unreadable. | **Broken** |
| **390 × 844** | Mobile Device | **Unusable**: Sidebar fails to collapse; navigation buttons push main content off-screen. Pipeline flowchart step nodes stack vertically or break bounds. | **Unusable** |

> [!IMPORTANT]
> **Design Verdict**: The current frontend is strictly **desktop-only** (`>= 1280px`). It lacks mobile media queries (`@media (max-width: 768px)`), collapsible sidebar navigation, or responsive table wrappers.

---

## 3. Part 2 — Information Architecture Audit

### 3.1 Current Navigation vs Recommended Grouping

Current navigation presents 8 flat, un-grouped tabs in the sidebar without hierarchical category demarcation:

```text
CURRENT FLAT NAVIGATION           RECOMMENDED GROUPED NAVIGATION
├── Curated Stories (Default)     PRODUCTION CONTROL CENTER
├── Setup & Sources               ├── 📊 Morning Overview (/overview)
├── Job Queue & Monitor           ├── 📖 Reddit Story Studio (/stories)
├── System Overview               ├── ⚡ Job Queue Monitor (/jobs) [Badge: 3 Failed]
├── Quality Gate Review           QUALITY & DISTRIBUTION
├── Exported Assets               ├── 🎬 Quality Gate Review (/review) [Badge: 4 Pending]
├── Background Footage            ├── 📁 Exported Assets Library (/assets)
├── Rights & Compliance           SYSTEM CONFIGURATION
                                  ├── ⚙️ Channels & Sources (/sources)
                                  ├── 🎞️ Background Video Pool (/backgrounds)
                                  ├── 🛡️ Rights & Compliance Audit (/rights)
                                  └── 🔔 System & Telegram Alerts (/settings)
```

### 3.2 Key Navigation Deficiencies
1. **Default Screen Misalignment**: Default view is `stories`. Operators opening the system in the morning should land on **Overview** to inspect queue health and system status before submitting stories.
2. **Missing Real-Time Badges**: Sidebar items do not display real-time counters. Operators must click into `candidates` to see if videos are waiting for review or `jobs` to see if jobs failed.
3. **Tab-State Navigation Loss**: State router relies on `useState('stories')`. Refreshing the browser or bookmarking resets the screen back to `stories`, discarding active filter inputs.

---

## 4. Part 3 — Operator-First Morning Control Center UX

When an operator opens YTAuto in the morning, they need immediate answers to 4 questions:
1. *Is the production engine healthy?* (Postgres, Redis, MinIO, llama-server).
2. *Are there videos waiting for my approval?* (Quality Gate Review Queue count).
3. *Did any background rendering jobs fail overnight?* (Failed/Dead-letter job count).
4. *How much YouTube API quota remains today?* (Remaining units tracker).

### 4.1 Comparison: Current vs Ideal Morning Overview

```text
+-----------------------------------------------------------------------------------+
| IDEAL MORNING CONTROL CENTER DASHBOARD                                            |
+-----------------------------------------------------------------------------------+
|  [ SYSTEM HEALTH: OK ]   [ QUEUE: 4 REVIEW READY ]   [ ALERTS: 1 FAILED JOB ]     |
+-----------------------------------------------------------------------------------+
|  SYSTEM INFRASTRUCTURE STATUS       |  OVERNIGHT PRODUCTION METRICS               |
|  • PostgreSQL: Connected            |  • Videos Processed Today: 18               |
|  • Redis Queue: 2 Active Jobs       |  • Stories Ingested: 12                     |
|  • MinIO Storage: 4.2 GB Used       |  • Render Failures: 1                       |
|  • llama-server (Vulkan): Healthy   |  • YouTube Quota Remaining: 8,450 / 10,000  |
+-------------------------------------+---------------------------------------------+
|  URGENT ACTION ITEMS REQUIRING ATTENTION                                          |
|  1. ⚠ Job #j_892f1 (narration) failed: Piper TTS binary timeout [Retry Button]   |
|  2. 🎬 4 Reddit Story videos awaiting your quality gate review [Review Now ->]    |
+-----------------------------------------------------------------------------------+
```

The current Overview tab (`activeTab === 'overview'`) displays basic infrastructure status cards, but lacks overnight metrics, direct quick-action links to failed jobs, or pending review counts.

---

## 5. Part 4 — Job Monitor UX Audit (`tab: jobs`)

### 5.1 Deficiencies in Current Job Monitor Table
1. **Monolithic Error Stack Traces**: Raw Python tracebacks (`Exception: FFmpeg exited with code 1 ...`) are dumped directly into table cells, bloating row height and confusing non-technical operators.
2. **No Elapsed Time or ETA**: Displays only static `created_at` timestamp. Does not show execution duration (e.g. `Running for 42s`) or estimated completion time.
3. **Lack of Automated Polling**: Table is static. Operators must manually click `Refresh Jobs` to check if a running job completed.
4. **Missing Job Details Drawer**: Clicking a job row does nothing. There is no expandable log viewer or detailed JSON inspection drawer.

---

## 6. Part 5 — Quality Gate / Video Review UX (`tab: candidates`)

### 6.1 The 50-Video Review Scenario
In high-volume automated production, an operator may need to review 50 rendered clips in a single session.

#### Current Bottlenecks:
- **No Keyboard Shortcuts**: Operator must move mouse to click `Approve` or `Reject` for every single video.
- **No Batch Actions**: No `Select All` or `Approve All High-Score Clips` controls.
- **No Fullscreen / Cinema Mode**: Video player is constrained to a fixed `260px` height card within a grid layout, making subtitle legibility testing difficult.
- **No Rejection Reason Input**: Clicking `Reject` immediately sets clip status to `rejected` without asking why (e.g., audio out of sync, bad subtitle wrap, low audio volume), preventing automated quality learning.

#### Proposed Reviewer Keyboard Ergonomics:
- `Space`: Play / Pause preview video.
- `A` or `Enter`: Approve clip for export (`status: ready`).
- `R` or `Backspace`: Open rejection reason modal & reject clip.
- `Right Arrow` / `Left Arrow`: Navigate to next / previous clip card.

---

## 7. Part 6 — Story Submission UX (`tab: stories`)

### 7.1 Form Usability Evaluation
- **Strengths**: Visual pipeline flowchart stepper clearly illustrates the 6 production stages from submit to local export.
- **Weaknesses**:
  1. *No Character / Word Count Estimator*: Reddit stories submitted to Piper TTS must fit within target video duration windows (30-60s for Shorts). The form does not calculate word count or estimated speech duration.
  2. *No Duplicate Detection*: Operators pasting the same Reddit story title twice are not warned prior to backend submission.
  3. *No Paste & Clean Utility*: Reddit posts frequently contain markdown headers (`# AITA`), edit updates (`EDIT: thanks for gold`), or user tags (`/u/username`). The submission box lacks an automated "Clean Reddit Formatting" button.

---

## 8. Part 7 — Complete Form Inventory Table

| Form Location | Form Purpose | Fields & Types | Required Fields | Client-Side Validation | Error Handling | Quality Rating |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `stories` tab | Submit Reddit Story | Title (text), Body (textarea), Channel (select), Subreddit (text), Author (text) | Title, Body | Basic empty string check | Toast notification (`toast-danger`) | **Fair** |
| `jobs` tab | Filter Jobs | Status Filter (buttons) | None | None | Silent console error | **Good** |
| `setup` tab | Create Channel Profile | Name (text), Slug (text), Niche (text), Project ID (text), Language (select) | Name, Slug | Empty string check | Toast notification | **Fair** |
| `setup` tab | Add Content Source | Source Type (select), External Ref (text), Poll Interval (number), Max Per Poll (number) | External Ref | HTML5 required | Toast notification | **Fair** |
| `overview` tab | Configure Telegram | Bot Token (password input), Chat ID (text input) | Both | Token & Chat ID required | Toast notification | **Good** |
| `assets` tab | Filter Exported Assets | Search Query (text input), Sort By (select), Category (select) | None | None | None (Client-side memo filter) | **Good** |
| `bgassets` tab | Upload Local Video | File Input (`accept="video/mp4"`) | File object | File presence check | Toast notification + loading state | **Good** |
| `bgassets` tab | Register YouTube URL | Source URL (text input) | URL string | HTML5 required | Toast notification | **Fair** |
| `rights` tab | Save Rights Compliance | Source ID (select), Status (select), Evidence Ref (text) | Source ID, Status | None | Toast notification | **Fair** |

---

## 9. Part 8 — Screen Lifecycle State Audit

| Screen Name | Initial Loading State | Empty State | Error State | Success Feedback | Manual Retry Option | Overall Quality |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **Curated Stories** | Missing (Instant mount) | Present (*"No stories submitted yet"*) | Toast alert | Toast alert + form reset | Present (*Re-queue All*) | **Fair** |
| **Job Queue Monitor** | Missing (Instant mount) | Present (*"No jobs found..."*) | Inline code text | Toast alert | Present (*Retry Job*) | **Good** |
| **Quality Gate Review** | Missing (Instant mount) | Present (*"No clips waiting..."*) | Toast alert | Toast alert | Missing | **Fair** |
| **Exported Assets** | Missing (Instant mount) | Present (*"No published clips..."*) | Toast alert | Toast alert | Present (*Sync/Re-export*) | **Good** |
| **Background Footage** | Upload Spinner present | Present (*"No background assets..."*) | Toast alert | Toast alert | Missing | **Good** |
| **Setup & Sources** | Missing (Instant mount) | Missing (Empty dropdown) | Toast alert | Toast alert | Missing | **Poor** |
| **System Overview** | Icon Spin Animation | N/A | Toast alert | Status Badges | Present (*Refresh Status*) | **Good** |
| **Rights & Compliance** | Missing (Instant mount) | Missing | Toast alert | Toast alert | Missing | **Poor** |

---

## 10. Part 9 — Accessibility (a11y) Audit Findings

All findings classified strictly by WCAG 2.1 severity:

### 10.1 Findings Table

| Severity | Issue Description | Source Code Location | Usability Impact |
| :--- | :--- | :--- | :--- |
| **CRITICAL** | **Icon-Only Buttons Missing `aria-label`**: Sidebar close icons (`<X size={14}>`), refresh icons (`<RefreshCw>`), and toast close buttons lack accessibility labels. | `App.tsx`: lines 543, 755, 808 | Screen readers announce unlabelled buttons as *"button"*, breaking non-visual navigation. |
| **HIGH** | **Low Contrast Color Ratios**: Secondary text (`--text-secondary: #94a3b8`) on dark glass cards (`rgba(30,41,59,0.7)`) yields a **3.4:1 contrast ratio**, failing WCAG AA minimum requirement (4.5:1). | `index.css`: line 5 | Muted metadata text is difficult to read under direct light or low-contrast monitors. |
| **HIGH** | **Color-Only Status Indicators**: Job statuses and infrastructure health rely solely on badge color (green/red/amber) without text descriptions or icons for colorblind operators. | `App.tsx`: lines 855-861, 1192-1202 | Protanopia/deuteranopia operators cannot distinguish `failed` from `succeeded` at a glance. |
| **MEDIUM** | **Missing Focus Ring Styles**: Inputs (`.input`) and buttons (`.btn`) remove browser outline on focus without providing a high-visibility replacement focus ring. | `index.css`: lines 163-165 | Keyboard navigation (`Tab` key) is invisible across form fields. |
| **MEDIUM** | **No Toast ARIA Live Region**: Toast notification container (`.toast-container`) lacks `aria-live="polite"` or `role="status"`. | `App.tsx`: line 533 | Screen readers fail to announce incoming alert notifications. |

---

## 11. Part 10 — Recommended Feature-Oriented Architecture

To resolve the maintenance risk of the 1,273-line `App.tsx` monolith, the frontend should be refactored into modular feature directories:

```text
C:\dev\YTAuto\frontend\src\
├── main.tsx                         # Entry point
├── index.css                        # Global Design Tokens & Utilities
├── routes.ts                        # Centralized Route Definitions
├── types/                           # TypeScript Interface Definitions
│   ├── channel.ts
│   ├── job.ts
│   ├── clip.ts
│   └── story.ts
├── services/                        # API Client Services
│   ├── api.ts                       # Base fetch wrapper & error interceptor
│   ├── jobs.service.ts
│   ├── clips.service.ts
│   └── stories.service.ts
├── hooks/                           # Custom React Hooks
│   ├── useJobs.ts                   # Auto-polling job hook
│   ├── useClips.ts                  # Review & asset clip hook
│   └── useToast.ts                  # Notification stack hook
├── components/                      # Reusable UI Design System Primitives
│   ├── ui/
│   │   ├── Button.tsx
│   │   ├── Badge.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   └── ToastStack.tsx
│   └── layout/
│       ├── AppShell.tsx             # Sidebar + Main Content Shell
│       ├── Sidebar.tsx
│       └── Header.tsx
└── features/                        # Domain Views & Feature Components
    ├── stories/
    │   ├── StoryStudioView.tsx
    │   ├── StorySubmissionForm.tsx
    │   └── StoryPipelineStepper.tsx
    ├── jobs/
    │   ├── JobMonitorView.tsx
    │   ├── JobStatusFilter.tsx
    │   ├── JobsTable.tsx
    │   └── JobDetailsDrawer.tsx
    ├── review/
    │   ├── QualityGateView.tsx
    │   ├── VideoPlayerCard.tsx
    │   └── RejectionReasonModal.tsx
    ├── assets/
    │   ├── AssetLibraryView.tsx
    │   └── AssetFilterToolbar.tsx
    └── overview/
        └── SystemOverviewView.tsx
```

---

## 12. Part 11 — Prioritized UX Backlog

| Priority | Issue / Defect Description | Affected View | Recommended Solution | Implementation Complexity |
| :---: | :--- | :--- | :--- | :---: |
| **P0** | **Monolithic `App.tsx` Maintenance Risk** | Entire Frontend | Refactor `App.tsx` into feature directories (`features/stories`, `features/jobs`, etc.). | Medium |
| **P0** | **Browser Refresh Screen Reset** | Application Shell | Implement HTML5 History URL routing (`/overview`, `/stories`, `/jobs`, `/review`, `/assets`). | Low |
| **P1** | **No Auto-Polling on Background Jobs** | `jobs` tab | Add custom `useJobs` hook with 5-second polling interval when `jobs` tab is active. | Low |
| **P1** | **No Keyboard Shortcuts for Review Queue** | `candidates` tab | Add keyboard event listener (`Space`, `A`, `R`, `ArrowRight`) for fast video review. | Low |
| **P1** | **Raw Python Traceback Exposure** | `jobs` tab | Parse backend errors into operator-friendly summaries; add "View Traceback" expander. | Low |
| **P2** | **Fixed Desktop Layout Breakage** | Layout (`index.css`) | Add media queries (`@media (max-width: 1024px)`) and collapsible mobile navigation drawer. | Medium |
| **P2** | **Low Contrast Secondary Text** | Global Design System | Darken `--bg-card` and increase `--text-secondary` contrast to `#cbd5e1` (7.1:1 ratio). | Low |
| **P2** | **Missing Character & Speech Duration Counter**| `stories` tab | Add real-time word count & estimated TTS duration indicator (`~45s speech duration`). | Low |
| **P3** | **No Rejection Reason Tracking** | `candidates` tab | Add rejection reason modal (`Bad Subtitles`, `Audio Desync`, `Low Quality`) before rejecting. | Medium |

---

## 13. Part 12 — Ideal Future UI Wireframes

### 13.1 Ideal Morning Overview Dashboard

```text
+-----------------------------------------------------------------------------------------------+
| YTAuto  v1.5                         [ 🟢 System Healthy ]   [ 🔔 Alerts (1) ]   [ 👤 Operator ] |
+-----------------------+-----------------------------------------------------------------------+
|  CONTROL CENTER       |  MORNING SYSTEM SUMMARY                                               |
|  📊 Overview          |  +-------------------+ +-------------------+ +---------------------+  |
|  📖 Story Studio      |  | 🎬 READY REVIEW   | | ⚡ ACTIVE JOBS    | | ⚠ FAILED JOBS       |  |
|  ⚡ Job Monitor  (3)   |  |   4 Videos        | |   2 Running       | |   1 Requires Retry  |  |
|                       |  +-------------------+ +-------------------+ +---------------------+  |
|  DISTRIBUTION         |                                                                       |
|  🎬 Quality Gate (4)  |  QUICK ACTIONS & ALERTS                                               |
|  📁 Exported Assets   |  • ⚠ Job #j_892 (piper_tts) failed: Audio timeout [ 🔄 Retry Job ]    |
|                       |  • 🎬 4 Reddit story videos passed QC [ ➔ Open Quality Review Gate ]  |
|  SYSTEM CONFIG        |                                                                       |
|  ⚙️ Sources           |  RESOURCE CAPACITY & RUNTIME                                          |
|  🎞️ Background Pool   |  • YouTube API Quota:  ██████████░░░░ 8,450 / 10,000 units             |
|  🛡️ Rights Audit     |  • Storage (MinIO):   ███░░░░░░░░░░░ 14.2 GB / 100 GB              |
|  🔔 System Alerts     |  • llama-server:      🟢 Qwen-3 (Vulkan GPU Acceleration Active)      |
+-----------------------+-----------------------------------------------------------------------+
```

### 13.2 Ideal Quality Gate Reviewer (Keyboard Optimized)

```text
+-----------------------------------------------------------------------------------------------+
| YTAuto  v1.5                                               Quality Gate Review (4 Pending)    |
+-----------------------+-----------------------------------------------------------------------+
|  CONTROL CENTER       |  VIDEO PREVIEW [ 1 of 4 ]                         SHORTCUTS:          |
|  📊 Overview          |  +-----------------------+  Clip ID: c_9821a   Space : Play/Pause   |
|  📖 Story Studio      |  |                       |  Type: Reddit Story  A / Enter : Approve   |
|  ⚡ Job Monitor       |  |   [ 9:16 VERTICAL     |  Duration: 42s      R / Del   : Reject    |
|                       |  |     PREVIEW VIDEO     |  Subreddit: r/AITA  ➔ / 🠔    : Navigate  |
|  DISTRIBUTION         |  |     PLAYER ]          |                                        |
|  🎬 Quality Gate (4)  |  |                       |  CAPTION PREVIEW:                      |
|  📁 Exported Assets   |  |   "AITA for refusing  |  Format: ASS Word Highlight            |
|                       |  |    my seat?"          |  Font: Arial Black (Yellow Pop)        |
|  SYSTEM CONFIG        |  |                       |                                        |
|  ⚙️ Sources           |  +-----------------------+  ACTION BUTTONS:                       |
|  🎞️ Background Pool   |  [ ◀ Previous ]             [ ❌ Reject (R) ]   [ ✅ Approve (A) ]   |
+-----------------------+-----------------------------------------------------------------------+
```

---

## 14. Final Product UX Verdict & Directives

### 14.1 Key Answers
1. **What is already excellent?**
   - The dark glassmorphic design system (`index.css`) establishes a sleek, modern visual baseline.
   - Floating toast notifications (`.toast-container`) provide non-intrusive feedback.
   - The Reddit story visual pipeline flowchart stepper cleanly communicates stage progression.
2. **What should NOT be changed?**
   - The dark slate color palette (`#0f172a` base, `#3b82f6` primary accent).
   - Core API payload contracts between frontend and FastAPI backend.
3. **What should definitely be changed?**
   - Refactor `App.tsx` (1,273 LOC) into modular feature components.
   - Switch from `useState('stories')` to HTML5 URL routing (`/overview`, `/stories`, `/jobs`, etc.).
   - Add real-time auto-polling to the Job Monitor.
   - Add keyboard shortcuts (`A`, `R`, `Space`) to the Quality Gate Video Reviewer.
4. **What would make YTAuto feel like a polished commercial product?**
   - Adding a unified **Morning Control Center Overview**, badge counters on sidebar navigation, auto-refreshing background jobs, and keyboard-driven video review workflows.
