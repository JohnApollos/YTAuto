import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { Job, Clip, SystemHealth, ModelHealth, Quota } from '../types';

export function useRealtimeData() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [reviewClips, setReviewClips] = useState<Clip[]>([]);
  const [publishedClips, setPublishedClips] = useState<Clip[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [models, setModels] = useState<Record<string, ModelHealth>>({});
  const [quotas, setQuotas] = useState<Quota[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRealtimeData = useCallback(async () => {
    try {
      const [jobsData, passedClips, pubClips, sysHealth, sysModels, sysQuotas] = await Promise.allSettled([
        api.getJobs('all'),
        api.getClips('qc_passed'),
        api.getClips('published'),
        api.getSystemHealth(),
        api.getModelHealth(),
        api.getQuotas()
      ]);

      if (jobsData.status === 'fulfilled') setJobs(jobsData.value);
      if (passedClips.status === 'fulfilled') setReviewClips(passedClips.value);
      if (pubClips.status === 'fulfilled') setPublishedClips(pubClips.value);
      if (sysHealth.status === 'fulfilled') setHealth(sysHealth.value);
      if (sysModels.status === 'fulfilled') setModels(sysModels.value);
      if (sysQuotas.status === 'fulfilled') setQuotas(sysQuotas.value);
    } catch (err) {
      console.error('Realtime fetch error:', err);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchRealtimeData().finally(() => setLoading(false));

    const interval = setInterval(fetchRealtimeData, 10000);
    return () => clearInterval(interval);
  }, [fetchRealtimeData]);

  const activeJobsCount = jobs.filter(j => j.status === 'running' || j.status === 'queued').length;
  const failedJobsCount = jobs.filter(j => j.status === 'failed' || j.status === 'dead_letter').length;
  const pendingReviewCount = reviewClips.length;

  return {
    jobs,
    reviewClips,
    publishedClips,
    health,
    models,
    quotas,
    loading,
    activeJobsCount,
    failedJobsCount,
    pendingReviewCount,
    refreshAll: fetchRealtimeData
  };
}
