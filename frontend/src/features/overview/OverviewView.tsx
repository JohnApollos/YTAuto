import React from 'react';
import type { RouteKey, SystemHealth, ModelHealth, Quota, Job, Clip } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Activity, CheckCircle, AlertTriangle, Play, RefreshCw, ArrowRight, Server, Cpu, Database, Film } from 'lucide-react';

interface OverviewViewProps {
  health: SystemHealth | null;
  models: Record<string, ModelHealth>;
  quotas: Quota[];
  jobs: Job[];
  reviewClips: Clip[];
  publishedClips: Clip[];
  onNavigate: (route: RouteKey) => void;
  onRefresh: () => void;
  onRetryJob: (jobId: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  health,
  models,
  quotas,
  jobs,
  reviewClips,
  publishedClips,
  onNavigate,
  onRefresh,
  onRetryJob
}) => {
  const activeJobs = jobs.filter(j => j.status === 'running' || j.status === 'queued');
  const failedJobs = jobs.filter(j => j.status === 'failed' || j.status === 'dead_letter');

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0 }}>
            <Activity /> Autonomous Production Command Center
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Real-time status of the automated production engine, system capacity, and operator action queue.
          </p>
        </div>
        <button onClick={onRefresh} className="btn btn-outline">
          <RefreshCw size={16} /> Refresh Command Center
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>System Infrastructure</span>
            <Server size={18} style={{ color: 'var(--accent-primary)' }} />
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 'bold', marginBottom: '8px' }}>
            {health?.db === 'ok' && health?.redis === 'ok' && health?.minio === 'ok' ? 'All Systems Healthy' : 'Degraded Infrastructure'}
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <Badge status={health?.db || 'ok'} /> DB
            <Badge status={health?.redis || 'ok'} /> Queue
            <Badge status={health?.minio || 'ok'} /> Storage
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', cursor: 'pointer' }} onClick={() => onNavigate('review')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Quality Review Gate</span>
            <CheckCircle size={18} style={{ color: 'var(--success)' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: reviewClips.length > 0 ? '#6ee7b7' : 'inherit' }}>
            {reviewClips.length} Clips
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '6px' }}>
            {reviewClips.length > 0 ? 'Ready for human approval' : 'Queue clear'} <ArrowRight size={12} />
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', cursor: 'pointer' }} onClick={() => onNavigate('jobs')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Active Production Queue</span>
            <Play size={18} style={{ color: 'var(--accent-primary)' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
            {activeJobs.length} Jobs
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
            {jobs.filter(j => j.status === 'running').length} currently executing
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', cursor: 'pointer' }} onClick={() => onNavigate('assets')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Exported Media Library</span>
            <Film size={18} style={{ color: '#93c5fd' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
            {publishedClips.length} Videos
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
            Stored in C:\dev\YTAuto\exports
          </div>
        </div>

      </div>

      <div className="glass-panel" style={{ marginBottom: '24px' }}>
        <h3 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem' }}>
          <AlertTriangle size={18} style={{ color: 'var(--warning)' }} /> Operator Attention & Urgent Actions
        </h3>

        {failedJobs.length === 0 && reviewClips.length === 0 ? (
          <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.9rem' }}>
            🟢 No urgent actions required. Autonomous pipeline is executing smoothly.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            
            {reviewClips.length > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px', background: 'rgba(16,185,129,0.1)', borderRadius: '10px', border: '1px solid rgba(16,185,129,0.3)' }}>
                <div>
                  <div style={{ fontWeight: 'bold', color: '#6ee7b7' }}>🎬 {reviewClips.length} Rendered Video(s) Ready for Quality Review</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    Rendered videos have passed automated QA checks and are waiting for final human approval.
                  </div>
                </div>
                <button onClick={() => onNavigate('review')} className="btn btn-success btn-sm">
                  Review Videos Now <ArrowRight size={14} />
                </button>
              </div>
            )}

            {failedJobs.map(j => (
              <div key={j.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px', background: 'rgba(239,68,68,0.1)', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.3)' }}>
                <div>
                  <div style={{ fontWeight: 'bold', color: '#fca5a5' }}>
                    ⚠️ Failed Pipeline Job: <span style={{ textTransform: 'capitalize' }}>{j.type.replace('_', ' ')}</span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px', fontFamily: 'monospace' }}>
                    Error: {j.error || 'Pipeline execution exception'}
                  </div>
                </div>
                <button onClick={() => onRetryJob(j.id)} className="btn btn-primary btn-sm">
                  <RefreshCw size={12} /> Retry Job
                </button>
              </div>
            ))}

          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        
        <div className="glass-panel">
          <h4 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} /> AI Model Runtime Residency
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {Object.keys(models).length === 0 ? (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                llama-server offline or in stub mode
              </div>
            ) : (
              Object.entries(models).map(([stage, status]) => (
                <div key={stage} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                  <span style={{ fontSize: '0.85rem', textTransform: 'capitalize' }}>Stage: {stage}</span>
                  <Badge status={status.healthy ? 'healthy' : 'offline'} />
                </div>
              ))
            )}
          </div>
        </div>

        <div className="glass-panel">
          <h4 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={16} /> YouTube API Quota Capacity
          </h4>
          {quotas.length === 0 ? (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              No API quota pools registered
            </div>
          ) : (
            quotas.map(q => (
              <div key={q.project_id} style={{ padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', marginBottom: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '6px' }}>
                  <span>Project: <code>{q.project_id}</code></span>
                  <span style={{ color: '#93c5fd', fontWeight: 'bold' }}>{q.remaining} units remaining</span>
                </div>
                <div style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, (q.remaining / 10000) * 100)}%`, height: '100%', background: 'var(--accent-primary)' }} />
                </div>
              </div>
            ))
          )}
        </div>

      </div>
    </div>
  );
};
