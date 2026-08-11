# YTAuto Frontend Route & Screen Inventory

## Overview
This document provides a detailed route-by-route inventory of all screens, state variations, parameters, and UI interactions in the YTAuto frontend application (`C:\dev\YTAuto\frontend\src\App.tsx`).

---

## 1. Route Map & Screen Details

### 1.1 Curated Reddit Stories Screen (`tab: stories`)
- **Visual Header**: `<BookOpen /> Curated Reddit Stories Production`
- **Subheader**: *"Submit Reddit stories or narratives for automated voice synthesis, subtitle rendering, and local export."*
- **Primary Actions**:
  - **Re-generate & Render All Stories (gTTS Voice)**: Triggers `POST /api/v1/curated-stories/re-queue-all`. Shows toast notification and re-fetches story list.
  - **Submit Story to Pipeline**: Validates required fields (`title`, `body_text`) and calls `POST /api/v1/curated-stories`.
- **Form Fields**:
  1. *Target Channel*: `<select>` dropdown populated from `channels` state (`GET /api/v1/channels/`).
  2. *Story Title*: `<input>` required string. Placeholder: *"Story Title (e.g. AITA for refusing to give my seat?)"*.
  3. *Story Body*: `<textarea>` 6 rows required text. Placeholder: *"Full story narrative body text..."*.
  4. *Subreddit*: `<input>` string. Default: `'r/AskReddit'`.
  5. *Author*: `<input>` optional string.
- **Pipeline Stepper Flowchart**:
  - Step 1: Operator Submit (`active`)
  - Step 2: LLM Script Format (`active`)
  - Step 3: Piper TTS Audio (`active`)
  - Step 4: Whisper ASS Subtitles (`active`)
  - Step 5: FFmpeg CC Crop Render (`active`)
  - Step 6: Local Export & `.txt` (`completed`)
- **Active Stories List**:
  - Shows submitted story cards with title, subreddit badge, and status pill (`done` -> green badge-completed, `failed` -> red badge-pending, `processing` -> blue badge-active).
  - Empty State: *"No stories submitted yet."*

---

### 1.2 Job Queue & Execution Monitor Screen (`tab: jobs`)
- **Visual Header**: `<Activity /> Job Queue & Execution Monitor`
- **Subheader**: *"Real-time visibility into all pipeline background jobs (queued, running, succeeded, failed, dead-letter)."*
- **Header Actions**:
  - **Flush Stuck Jobs**: Calls `POST /api/v1/system/jobs/flush-stuck` to reset stale heartbeat jobs back to queued status.
  - **Refresh Jobs**: Re-queries `GET /api/v1/jobs` with the current status filter.
- **Status Filter Toolbar**:
  - Tabs: `all`, `queued`, `running`, `succeeded`, `failed`, `dead_letter`, `cancelled`.
  - Shows real-time badge count for each status pill.
- **Jobs Table Columns**:
  1. *Job Type & Trace ID*: Displays formatted job type (e.g., `script_preparation`, `narration`, `rendering`) and UUID trace identifier in monospace.
  2. *Status*: Color-coded badge pill.
  3. *Attempts*: Current attempt count vs max attempts (e.g., `1 / 3`).
  4. *Error Details*: Formatted stack error string in red monospace font (`#fca5a5`).
  5. *Created At*: Formatted timestamp string (`toLocaleString()`).
  6. *Actions*: **Retry Job** button (`POST /api/v1/jobs/{job_id}/retry`) rendered for failed or dead-letter jobs.
- **Empty State**: *"No jobs found for status filter [filter]"*.

---

### 1.3 Quality Gate Review Queue Screen (`tab: candidates`)
- **Visual Header**: `<Activity /> Quality Gate Review Queue`
- **Subheader**: *"Preview rendered videos, listen to voice narration, verify subtitles, and approve or reject clips before local export."*
- **Grid Layout**: Responsive card grid (`.grid-cards`).
- **Clip Card Elements**:
  - **HTML5 Video Player**: `<video src="/api/v1/clips/{clip_id}/video" controls preload="metadata">`. Plays vertical rendered MP4 video with burned-in ASS captions.
  - **Clip Info**: Truncated Clip ID, Content Type badge (`📖 Reddit Story` or `🎙️ Podcast Clip`), and Duration (`clip.duration_s`).
  - **Action Buttons**:
    - **Approve (Publish)** (`.btn-success`): Calls `PATCH /api/v1/clips/{clip_id}` with `{status: "ready"}`.
    - **Reject** (`.btn-outline` danger color): Calls `PATCH /api/v1/clips/{clip_id}` with `{status: "rejected"}`.
- **Empty State**: *"No clips waiting in the review queue."*

---

### 1.4 Exported Assets Library Screen (`tab: assets`)
- **Visual Header**: `<FolderCheck /> Local Exported Assets Library`
- **Location Badge**: `C:\dev\YTAuto\exports\`
- **Header Action**:
  - **Sync / Re-export All Files to Folder**: Triggers `POST /api/v1/system/re-export` to flush all published video files into the local exports directory with unique filenames.
- **Toolbar Controls**:
  1. *Search Input*: Filter by Clip ID substring (`assetSearchQuery`).
  2. *Sort Selector*: `date_desc` (Newest First), `date_asc` (Oldest First), `duration_desc` (Longest First), `duration_asc` (Shortest First).
  3. *Category Selector*: `all`, `youtube_clip` (Podcast clips), `reddit_story` (Story videos).
- **Asset Grid Cards**:
  - HTML5 video player, Clip ID, Exported status badge, Category label, Duration, and Creation Date.
- **Empty State**: *"No published clips found matching your filters."*

---

### 1.5 Background Video Assets Screen (`tab: bgassets`)
- **Visual Header**: `<Film /> Background Video Assets Library`
- **Upload / Register Options**:
  - **Option 1: Upload Local Video File (.mp4)**: File input (`accept="video/mp4"`) invoking `POST /api/v1/background-assets/upload` via `FormData`. Displays *"Uploading Video..."* loading spinner state.
  - **Option 2: Register YouTube CC Video URL**: URL input form submitting `POST /api/v1/background-assets` with `{source_url, license_type: "licensed"}`.
- **Registered Pool Grid**:
  - Displays registered asset cards with `source_url`, status badge (`ready`, `downloading`), and MinIO `storage_key`.
- **Empty State**: *"No background assets registered yet. Upload an .mp4 file or register a YouTube URL above!"*

---

### 1.6 Setup & Sources Screen (`tab: setup`)
- **Visual Header**: `<Settings /> Setup Channels & Content Sources`
- **Section A: Channel Management**:
  - Form to add new channel profile (`name`, `slug`, `niche`, `project_id`, `language`). Calls `POST /api/v1/channels/`.
- **Section B: Content Sources**:
  - Active Channel dropdown selector.
  - Form to add new content source (`type`: `youtube_channel` or `curated_story`, `external_ref`, `poll_interval_minutes`, `max_new_videos_per_poll`). Calls `POST /api/v1/sources/`.
  - Source list cards with **Pause** / **Activate** toggle button (`PATCH /api/v1/sources/{source_id}`).

---

### 1.7 System Overview & Telegram Config Screen (`tab: overview`)
- **Visual Header**: `<LayoutDashboard /> System Health & Status`
- **Header Action**: **Refresh Status** button (spins icon while loading `healthLoading`).
- **Cards & Status Monitors**:
  - **System Infrastructure**: PostgreSQL, Redis, and MinIO health badges (`ok` -> green, `error` -> red).
  - **Model Runtime Status**: Lists LLM stages (`intelligence`, `narration`, etc.) with model name and health state (`Healthy` / `Offline`).
  - **YouTube Quota Pools**: Displays project IDs and remaining API quota units.
  - **Telegram Bot Real-Time Alerts Form**:
    - Inputs for Telegram Bot Token (password input) and Chat ID (`text` input).
    - **Test & Save Telegram Alert** button: Calls `POST /api/v1/system/telegram/test` to verify bot credentials and send an instant test push notification.

---

### 1.8 Rights & Compliance Screen (`tab: rights`)
- **Visual Header**: `<Shield /> Rights & Compliance Audit`
- **Form Fields**:
  1. *Content Source Selector*: Selects target source from `sources` list.
  2. *Rights Status Selector*: Dropdown options (`owned`, `licensed`, `permission_granted`, `unknown`, `denied`).
  3. *Evidence Reference*: `<input>` string for documentation URLs or license notes.
- **Action**: **Save Compliance Audit Record** button submitting `POST /api/v1/rights/{source_id}`. Shows success toast notification upon save.
