import type { Channel, ContentSource, Clip, Quota, ModelHealth, SystemHealth, Job, CuratedStory, BackgroundAsset } from '../types';

export const API_BASE = window.location.origin.includes('5173') || window.location.origin.includes('3000')
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const errData = await res.json();
      message = errData.detail || errData.message || message;
    } catch {
      // Fallback
    }
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  async getChannels(): Promise<Channel[]> {
    const res = await fetch(`${API_BASE}/channels/`);
    const data = await handleResponse<{ channels: Channel[] }>(res);
    return data.channels || [];
  },

  async createChannel(payload: { name: string; slug: string; niche?: string; project_id?: string; language?: string }): Promise<Channel> {
    const res = await fetch(`${API_BASE}/channels/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse<Channel>(res);
  },

  async getSources(channelId: string): Promise<ContentSource[]> {
    if (!channelId) return [];
    const res = await fetch(`${API_BASE}/sources/?channel_id=${channelId}`);
    const data = await handleResponse<{ sources: ContentSource[] }>(res);
    return data.sources || [];
  },

  async createSource(payload: { channel_id: string; type: string; external_ref: string; config: any }): Promise<ContentSource> {
    const res = await fetch(`${API_BASE}/sources/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse<ContentSource>(res);
  },

  async updateSourceActive(sourceId: string, active: boolean): Promise<ContentSource> {
    const res = await fetch(`${API_BASE}/sources/${sourceId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active })
    });
    return handleResponse<ContentSource>(res);
  },

  async getRightsStatus(sourceId: string): Promise<{ status: string; evidence_ref?: string }> {
    const res = await fetch(`${API_BASE}/rights/${sourceId}`);
    return handleResponse(res);
  },

  async saveRightsStatus(sourceId: string, status: string, evidenceRef: string): Promise<any> {
    const res = await fetch(`${API_BASE}/rights/${sourceId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, evidence_ref: evidenceRef, reviewed_by: 'Operator' })
    });
    return handleResponse(res);
  },

  async getSystemHealth(): Promise<SystemHealth> {
    const res = await fetch(`${API_BASE}/system/health`);
    return handleResponse<SystemHealth>(res);
  },

  async getSystemResources(): Promise<import('../types').SystemResources> {
    const res = await fetch(`${API_BASE}/system/resources`);
    return handleResponse<import('../types').SystemResources>(res);
  },

  async getModelHealth(): Promise<Record<string, ModelHealth>> {
    const res = await fetch(`${API_BASE}/system/models`);
    const data = await handleResponse<{ models: Record<string, ModelHealth> }>(res);
    return data.models || {};
  },

  async getQuotas(): Promise<Quota[]> {
    const res = await fetch(`${API_BASE}/system/quota`);
    const data = await handleResponse<{ quotas: Quota[] }>(res);
    return data.quotas || [];
  },

  async getTelegramConfig(): Promise<any> {
    const res = await fetch(`${API_BASE}/system/telegram`);
    return handleResponse(res);
  },

  async saveTelegramConfig(bot_token: string, chat_id: string, allowed_chat_ids?: string[]): Promise<any> {
    const res = await fetch(`${API_BASE}/system/telegram`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token, chat_id, allowed_chat_ids })
    });
    return handleResponse(res);
  },

  async saveTelegramPreferences(payload: any): Promise<any> {
    const res = await fetch(`${API_BASE}/system/telegram/preferences`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse(res);
  },

  async testTelegram(bot_token: string, chat_id: string): Promise<any> {
    const res = await fetch(`${API_BASE}/system/telegram/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token, chat_id })
    });
    return handleResponse(res);
  },

  async getTelegramLogs(limit: number = 20): Promise<any> {
    const res = await fetch(`${API_BASE}/system/telegram/logs?limit=${limit}`);
    return handleResponse(res);
  },

  async getJobs(statusFilter: string = 'all'): Promise<Job[]> {
    const url = statusFilter && statusFilter !== 'all'
      ? `${API_BASE}/jobs?status=${statusFilter}`
      : `${API_BASE}/jobs`;
    const res = await fetch(url);
    const data = await handleResponse<{ jobs: Job[] }>(res);
    return data.jobs || [];
  },

  async retryJob(jobId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/retry`, { method: 'POST' });
    return handleResponse(res);
  },

  async flushStuckJobs(): Promise<{ flushed_jobs: number }> {
    const res = await fetch(`${API_BASE}/system/jobs/flush-stuck`, { method: 'POST' });
    return handleResponse(res);
  },

  async getClips(status: 'qc_passed' | 'published' | 'ready' | 'rejected'): Promise<Clip[]> {
    const res = await fetch(`${API_BASE}/clips/?status=${status}`);
    const data = await handleResponse<{ clips: Clip[] }>(res);
    return data.clips || [];
  },

  async updateClipStatus(clipId: string, status: 'ready' | 'rejected'): Promise<Clip> {
    const res = await fetch(`${API_BASE}/clips/${clipId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    return handleResponse<Clip>(res);
  },

  async reExportClips(): Promise<{ re_exported_clips: number }> {
    const res = await fetch(`${API_BASE}/system/re-export`, { method: 'POST' });
    return handleResponse(res);
  },

  async flushRawStorage(): Promise<{ deleted_objects: number; freed_mb: number; purged_videos: number }> {
    const res = await fetch(`${API_BASE}/system/storage/flush-raw`, { method: 'POST' });
    return handleResponse(res);
  },

  async purgeAgedAssets(days: number = 7): Promise<{ deleted_objects: number; freed_mb: number; freed_gb: number; purged_clips: number; purged_jobs: number }> {
    const res = await fetch(`${API_BASE}/system/storage/purge-aged?days=${days}`, { method: 'POST' });
    return handleResponse(res);
  },

  async getCuratedStories(): Promise<CuratedStory[]> {
    const res = await fetch(`${API_BASE}/curated-stories`);
    return handleResponse<CuratedStory[]>(res);
  },

  async submitCuratedStory(payload: { title: string; body_text: string; subreddit?: string; author?: string; channel_id?: string }): Promise<CuratedStory> {
    const res = await fetch(`${API_BASE}/curated-stories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse<CuratedStory>(res);
  },

  async reQueueAllStories(): Promise<{ requeued_stories: number }> {
    const res = await fetch(`${API_BASE}/curated-stories/re-queue-all`, { method: 'POST' });
    return handleResponse(res);
  },

  async scoutRedditStoriesNow(): Promise<{ status: string; enqueued_jobs: string[] }> {
    const res = await fetch(`${API_BASE}/curated-stories/scout-now`, { method: 'POST' });
    return handleResponse(res);
  },

  async pollSourceNow(sourceId: string): Promise<{ status: string; job_id: string; trace_id: string }> {
    const res = await fetch(`${API_BASE}/sources/${sourceId}/poll-now`, { method: 'POST' });
    return handleResponse(res);
  },

  async getBackgroundAssets(): Promise<BackgroundAsset[]> {
    const res = await fetch(`${API_BASE}/background-assets`);
    return handleResponse<BackgroundAsset[]>(res);
  },

  async registerBackgroundUrl(source_url: string): Promise<BackgroundAsset> {
    const res = await fetch(`${API_BASE}/background-assets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_url, license_type: 'licensed' })
    });
    return handleResponse<BackgroundAsset>(res);
  },

  async uploadBackgroundFile(file: File): Promise<BackgroundAsset> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('license_type', 'owned');
    const res = await fetch(`${API_BASE}/background-assets/upload`, {
      method: 'POST',
      body: formData
    });
    return handleResponse<BackgroundAsset>(res);
  }
};
