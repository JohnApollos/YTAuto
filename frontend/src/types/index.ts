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
