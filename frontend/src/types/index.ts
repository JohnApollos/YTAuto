export interface Channel {
  id: string;
  name: string;
  slug: string;
  niche: string;
  status: string;
  project_id: string;
  language: string;
}

export interface ContentSource {
  id: string;
  channel_id: string;
  type: string;
  external_ref: string;
  active: boolean;
  last_polled_at: string | null;
  config: any;
}

export interface Clip {
  id: string;
  channel_id: string;
  status: string;
  duration_s: number;
  created_at: string | null;
  scores: any;
  source_post_id?: string;
  storage_key?: string;
}

export interface Quota {
  project_id: string;
  remaining: number;
  error?: string;
}

export interface ModelHealth {
  healthy: boolean;
  model_name: string;
  message: string;
}

export interface SystemHealth {
  db: string;
  redis: string;
  minio: string;
}

export interface Job {
  id: string;
  type: string;
  status: string;
  trace_id: string;
  display_title?: string;
  attempts: number;
  max_attempts: number;
  error?: string;
  created_at: string;
  updated_at?: string;
  last_heartbeat_at?: string;
  payload?: any;
}

export interface CuratedStory {
  id: string;
  title: string;
  body_text: string;
  status: string;
  subreddit?: string;
  author?: string;
  channel_id?: string;
  created_at?: string;
}

export interface BackgroundAsset {
  id: string;
  source_url: string;
  license_type: string;
  status: string;
  storage_key?: string;
  created_at?: string;
}

export interface ToastItem {
  id: string;
  type: 'success' | 'danger' | 'warning' | 'info';
  text: string;
  title?: string;
  actionRoute?: string;
}

export interface CPUStats {
  percent: number;
  cores_physical: number;
  cores_logical: number;
  model_name: string;
}

export interface RAMStats {
  used_gb: number;
  total_gb: number;
  free_gb: number;
  percent: number;
}

export interface GPUStats {
  name: string;
  used_vram_gb: number;
  total_vram_gb: number;
  free_vram_gb: number;
  percent: number;
}

export interface StorageStats {
  total_disk_gb: number;
  used_disk_gb: number;
  disk_percent: number;
  exports_mb: number;
  renders_mb: number;
  raw_mb: number;
  transcripts_mb: number;
}

export interface CoexistenceStats {
  status: 'optimal' | 'contended' | 'critical';
  message: string;
  headroom_ram_gb: number;
  headroom_vram_gb: number;
}

export interface StageProfileEntry {
  id: string;
  stage: string;
  job_id: string;
  trace_id: string;
  display_title?: string;
  duration_s: number;
  cpu_percent: number;
  start_ram_mb: number;
  peak_ram_mb: number;
  ram_delta_mb: number;
  start_vram_mb: number;
  peak_vram_mb: number;
  vram_delta_mb: number;
  timestamp: string;
  tokens_generated?: number;
  prompt_tokens?: number;
  tokens_per_sec?: number;
  status: string;
  error?: string;
}

export interface StageAverage {
  count: number;
  avg_duration_s: number;
  avg_peak_ram_mb: number;
  avg_peak_vram_mb: number;
}

export interface SystemResources {
  cpu: CPUStats;
  ram: RAMStats;
  gpu: GPUStats;
  storage: StorageStats;
  coexistence: CoexistenceStats;
  recent_profiles: StageProfileEntry[];
  stage_averages: Record<string, StageAverage>;
}

export type RouteKey = 
  | 'overview' 
  | 'stories' 
  | 'jobs' 
  | 'review' 
  | 'assets' 
  | 'backgrounds' 
  | 'sources' 
  | 'rights' 
  | 'settings';

