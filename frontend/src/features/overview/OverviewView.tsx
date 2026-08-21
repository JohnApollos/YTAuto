import React from 'react';
import type { RouteKey, SystemHealth, SystemResources, ModelHealth, Quota, Job, Clip } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { 
  Activity, 
  CheckCircle, 
  AlertTriangle, 
  Play, 
  RefreshCw, 
  ArrowRight, 
  Server, 
  Cpu, 
  Database, 
  Film,
  HardDrive,
  Zap,
  Clock,
  Gauge
} from 'lucide-react';

interface OverviewViewProps {
  health: SystemHealth | null;
  resources: SystemResources | null;
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
  resources,
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

  // Helper for progress bar color
  const getUsageColor = (percent: number) => {
    if (percent < 65) return '#10b981'; // Green
    if (percent < 85) return '#f59e0b'; // Amber
    return '#ef4444'; // Red
  };

  const coexistenceStatus = resources?.coexistence?.status || 'optimal';
  const coexistenceBadgeColor = 
    coexistenceStatus === 'optimal' ? 'rgba(16,185,129,0.15)' :
    coexistenceStatus === 'contended' ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)';
  const coexistenceBorderColor = 
    coexistenceStatus === 'optimal' ? 'rgba(16,185,129,0.4)' :
    coexistenceStatus === 'contended' ? 'rgba(245,158,11,0.4)' : 'rgba(239,68,68,0.4)';
  const coexistenceTextColor = 
    coexistenceStatus === 'optimal' ? '#6ee7b7' :
    coexistenceStatus === 'contended' ? '#fcd34d' : '#fca5a5';

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Activity /> Autonomous Production Command Center
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Real-time telemetry, hardware capacity, and pipeline throughput for YTAuto & OpenWorker coexistence.
          </p>
        </div>
        <button onClick={onRefresh} className="btn btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <RefreshCw size={16} /> Refresh Metrics
        </button>
      </div>

      {/* Top 4 KPI Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Infrastructure State</span>
            <Server size={18} style={{ color: 'var(--accent-primary)' }} />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 'bold', marginBottom: '8px' }}>
            {health?.db === 'ok' && health?.redis === 'ok' && health?.minio === 'ok' ? 'All Systems Healthy' : 'Degraded Infrastructure'}
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <Badge status={health?.db || 'ok'} /> DB
            <Badge status={health?.redis || 'ok'} /> Queue
            <Badge status={health?.minio || 'ok'} /> MinIO
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
            {reviewClips.length > 0 ? 'Ready for human review' : 'Queue clear'} <ArrowRight size={12} />
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', cursor: 'pointer' }} onClick={() => onNavigate('jobs')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Active Pipeline Queue</span>
            <Play size={18} style={{ color: 'var(--accent-primary)' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
            {activeJobs.length} Jobs
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
            {jobs.filter(j => j.status === 'running').length} executing | {jobs.filter(j => j.status === 'queued').length} queued
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

      {/* HARDWARE RESOURCE CONSUMPTION & COEXISTENCE GOVERNOR */}
      <div className="glass-panel" style={{ marginBottom: '24px', padding: '22px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap', gap: '10px' }}>
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.15rem' }}>
            <Gauge size={20} style={{ color: 'var(--accent-primary)' }} /> Real-Time Hardware Resource Consumption
          </h3>
          
          {/* Coexistence Badge */}
          <div style={{ 
            padding: '6px 14px', 
            borderRadius: '20px', 
            background: coexistenceBadgeColor, 
            border: `1px solid ${coexistenceBorderColor}`,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.82rem',
            fontWeight: '600',
            color: coexistenceTextColor
          }}>
            <Zap size={14} />
            Coexistence: {coexistenceStatus.toUpperCase()} — {resources?.coexistence?.message || 'Host telemetry operational'}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '18px' }}>
          
          {/* CPU Gauge */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '8px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                <Cpu size={15} /> CPU Utilization
              </span>
              <span style={{ fontWeight: 'bold', color: getUsageColor(resources?.cpu?.percent || 0) }}>
                {resources?.cpu?.percent?.toFixed(1) || 0}%
              </span>
            </div>
            <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
              <div style={{ 
                width: `${Math.min(100, Math.max(2, resources?.cpu?.percent || 0))}%`, 
                height: '100%', 
                background: getUsageColor(resources?.cpu?.percent || 0),
                transition: 'width 0.4s ease'
              }} />
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              {resources?.cpu?.model_name || 'Ryzen 5 5500 (12 Threads)'}
            </div>
          </div>

          {/* System RAM Gauge */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '8px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                <HardDrive size={15} /> System RAM
              </span>
              <span style={{ fontWeight: 'bold', color: getUsageColor(resources?.ram?.percent || 0) }}>
                {resources?.ram?.used_gb || 0} / {resources?.ram?.total_gb || 16} GB
              </span>
            </div>
            <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
              <div style={{ 
                width: `${Math.min(100, Math.max(2, resources?.ram?.percent || 0))}%`, 
                height: '100%', 
                background: getUsageColor(resources?.ram?.percent || 0),
                transition: 'width 0.4s ease'
              }} />
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Available Headroom: <b>{resources?.ram?.free_gb || 0} GB</b>
            </div>
          </div>

          {/* GPU VRAM Gauge */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '8px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                <Activity size={15} /> GPU VRAM
              </span>
              <span style={{ fontWeight: 'bold', color: getUsageColor(resources?.gpu?.percent || 0) }}>
                {resources?.gpu?.used_vram_gb || 0} / {resources?.gpu?.total_vram_gb || 8} GB
              </span>
            </div>
            <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
              <div style={{ 
                width: `${Math.min(100, Math.max(2, resources?.gpu?.percent || 0))}%`, 
                height: '100%', 
                background: getUsageColor(resources?.gpu?.percent || 0),
                transition: 'width 0.4s ease'
              }} />
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              {resources?.gpu?.name || 'AMD Radeon RX 580 (8GB)'}
            </div>
          </div>

          {/* Disk Footprint */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '8px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                <HardDrive size={15} /> Storage Footprint
              </span>
              <span style={{ fontWeight: 'bold', color: '#93c5fd' }}>
                {resources?.storage?.used_disk_gb || 0} GB used
              </span>
            </div>
            <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
              <div style={{ 
                width: `${Math.min(100, Math.max(2, resources?.storage?.disk_percent || 0))}%`, 
                height: '100%', 
                background: 'var(--accent-primary)',
                transition: 'width 0.4s ease'
              }} />
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Exports: {((resources?.storage?.exports_mb || 0) / 1024).toFixed(1)} GB | MinIO: {((resources?.storage?.renders_mb || 0) / 1024).toFixed(1)} GB
            </div>
          </div>

        </div>
      </div>

      {/* Operator Attention Card */}
      <div className="glass-panel" style={{ marginBottom: '24px' }}>
        <h3 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem' }}>
          <AlertTriangle size={18} style={{ color: 'var(--warning)' }} /> Operator Attention & Urgent Actions
        </h3>

        {failedJobs.length === 0 && reviewClips.length === 0 ? (
          <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.9rem' }}>
            🟢 No urgent actions required. Autonomous pipeline is operating cleanly.
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

      {/* STAGE EXECUTION PROFILES & BENCHMARKS */}
      {resources?.recent_profiles && resources.recent_profiles.length > 0 && (
        <div className="glass-panel" style={{ marginBottom: '24px' }}>
          <h4 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.05rem' }}>
            <Clock size={16} style={{ color: 'var(--accent-primary)' }} /> Recent Pipeline Stage Execution Latency & Profiling
          </h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '8px 12px' }}>Stage</th>
                  <th style={{ padding: '8px 12px' }}>Video / Target Item & Trace ID</th>
                  <th style={{ padding: '8px 12px' }}>Duration</th>
                  <th style={{ padding: '8px 12px' }}>Peak RAM</th>
                  <th style={{ padding: '8px 12px' }}>Peak VRAM</th>
                  <th style={{ padding: '8px 12px' }}>Tokens / Speed</th>
                  <th style={{ padding: '8px 12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {resources.recent_profiles.slice(0, 8).map(p => (
                  <tr key={p.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                    <td style={{ padding: '10px 12px', fontWeight: '600', textTransform: 'capitalize' }}>
                      {p.stage.replace('_', ' ')}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {p.display_title ? (
                        <div>
                          <div style={{ fontWeight: '600', color: '#f8fafc', fontSize: '0.84rem', maxWidth: '340px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {p.display_title}
                          </div>
                          <div style={{ fontSize: '0.72rem', fontFamily: 'monospace', color: 'var(--text-secondary)', marginTop: '2px' }}>
                            {p.trace_id || p.job_id || '-'}
                          </div>
                        </div>
                      ) : (
                        <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                          {p.trace_id || p.job_id || '-'}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 'bold', color: '#93c5fd' }}>
                      {p.duration_s.toFixed(2)}s
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                      {p.peak_ram_mb.toFixed(0)} MB
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                      {p.peak_vram_mb.toFixed(0)} MB
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                      {p.tokens_per_sec ? `${p.tokens_per_sec} tok/s (${p.tokens_generated} tok)` : '-'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <Badge status={p.status === 'completed' ? 'succeeded' : 'failed'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Model Residency & Quota Pools */}
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
                  <span style={{ fontSize: '0.85rem', textTransform: 'capitalize' }}>Stage: {stage.replace('_', ' ')}</span>
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
                  <span style={{ color: '#93c5fd', fontWeight: 'bold' }}>{q.remaining.toLocaleString()} units remaining</span>
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
