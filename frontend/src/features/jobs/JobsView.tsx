import React, { useState, useMemo } from 'react';
import type { Job } from '../../types';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Activity, RefreshCw, Code, Search, AlertOctagon, Copy, Check } from 'lucide-react';

interface JobsViewProps {
  jobs: Job[];
  onRefreshJobs: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const JobsView: React.FC<JobsViewProps> = ({ jobs, onRefreshJobs, showToast }) => {
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTechJob, setSelectedTechJob] = useState<Job | null>(null);
  const [copied, setCopied] = useState(false);

  const filteredJobs = useMemo(() => {
    return jobs.filter(j => {
      const matchesStatus = statusFilter === 'all' || j.status === statusFilter;
      const query = searchQuery.toLowerCase().trim();
      const matchesQuery = !query || 
        j.id.toLowerCase().includes(query) ||
        j.type.toLowerCase().includes(query) ||
        j.trace_id.toLowerCase().includes(query) ||
        (j.error && j.error.toLowerCase().includes(query));
      return matchesStatus && matchesQuery;
    });
  }, [jobs, statusFilter, searchQuery]);

  const failedJobs = jobs.filter(j => j.status === 'failed' || j.status === 'dead_letter');

  const handleRetry = async (jobId: string) => {
    try {
      await api.retryJob(jobId);
      showToast('Job re-queued successfully!', 'success');
      onRefreshJobs();
    } catch (err: any) {
      showToast(err.message || 'Failed to retry job', 'danger');
    }
  };

  const handleRetryAllFailed = async () => {
    if (failedJobs.length === 0) {
      showToast('No failed jobs to retry', 'info');
      return;
    }
    showToast(`Re-queuing ${failedJobs.length} failed jobs...`, 'info');
    let successCount = 0;
    for (const j of failedJobs) {
      try {
        await api.retryJob(j.id);
        successCount++;
      } catch (e) {
        // continue
      }
    }
    showToast(`Successfully re-queued ${successCount} jobs!`, 'success');
    onRefreshJobs();
  };

  const handleFlushStuck = async () => {
    try {
      showToast('Flushing stuck jobs back to queue...', 'info');
      const data = await api.flushStuckJobs();
      showToast(`Flushed ${data.flushed_jobs} stuck jobs!`, 'success');
      onRefreshJobs();
    } catch (err: any) {
      showToast(err.message || 'Failed to flush jobs', 'danger');
    }
  };

  const handleCopyPayload = (data: any) => {
    navigator.clipboard.writeText(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    showToast('Copied to clipboard', 'info');
  };

  const formatElapsed = (createdStr?: string, heartbeatStr?: string, status?: string) => {
    if (!createdStr) return '-';
    const start = new Date(createdStr.endsWith('Z') ? createdStr : createdStr + 'Z').getTime();
    const end = (status === 'running' || status === 'queued') ? Date.now() : (heartbeatStr ? new Date(heartbeatStr.endsWith('Z') ? heartbeatStr : heartbeatStr + 'Z').getTime() : Date.now());
    const diffSec = Math.max(0, Math.floor((end - start) / 1000));
    if (diffSec < 60) return `${diffSec}s`;
    const mins = Math.floor(diffSec / 60);
    const secs = diffSec % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Activity /> Production Queue & Execution Monitor
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Real-time queue depth, retry controls, and execution trace inspection.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {failedJobs.length > 0 && (
            <button className="btn btn-outline" style={{ borderColor: 'rgba(239,68,68,0.4)', color: '#fca5a5' }} onClick={handleRetryAllFailed}>
              <AlertOctagon size={16} /> Retry All Failed ({failedJobs.length})
            </button>
          )}
          <button className="btn btn-outline" onClick={handleFlushStuck}>
            <RefreshCw size={16} /> Flush Stuck Jobs
          </button>
          <button className="btn btn-primary" onClick={onRefreshJobs}>
            <RefreshCw size={16} /> Refresh Queue
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', gap: '14px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {['all', 'queued', 'running', 'succeeded', 'failed', 'dead_letter'].map(st => {
            const count = st === 'all' ? jobs.length : jobs.filter(j => j.status === st).length;
            return (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`btn btn-sm ${statusFilter === st ? 'btn-primary' : 'btn-outline'}`}
                style={{ textTransform: 'capitalize' }}
              >
                {st.replace('_', ' ')}
                <span style={{ marginLeft: '6px', opacity: 0.8, fontSize: '0.75rem' }}>({count})</span>
              </button>
            );
          })}
        </div>

        <div style={{ position: 'relative', minWidth: '260px' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
          <input
            type="text"
            className="form-control"
            placeholder="Search by ID, stage, or error..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '36px', height: '36px', fontSize: '0.85rem' }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        {filteredJobs.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            No background jobs found matching the current filters.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.05)', borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '14px 18px' }}>Pipeline Stage & Trace ID</th>
                <th style={{ padding: '14px 18px' }}>Status</th>
                <th style={{ padding: '14px 18px' }}>Attempts</th>
                <th style={{ padding: '14px 18px' }}>Elapsed</th>
                <th style={{ padding: '14px 18px' }}>Error / Summary</th>
                <th style={{ padding: '14px 18px' }}>Created At</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map(j => (
                <tr key={j.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <td style={{ padding: '14px 18px' }}>
                    <div style={{ fontWeight: '600', color: '#f8fafc', textTransform: 'capitalize' }}>
                      {j.type.replace('_', ' ')}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'monospace', marginTop: '2px' }}>
                      {j.trace_id}
                    </div>
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <Badge status={j.status} />
                  </td>
                  <td style={{ padding: '14px 18px', fontFamily: 'monospace' }}>
                    {j.attempts} / {j.max_attempts}
                  </td>
                  <td style={{ padding: '14px 18px', color: '#93c5fd', fontFamily: 'monospace' }}>
                    {formatElapsed(j.created_at, j.last_heartbeat_at, j.status)}
                  </td>
                  <td style={{ padding: '14px 18px', maxWidth: '300px' }}>
                    {j.error ? (
                      <div>
                        <div style={{ color: '#fca5a5', fontSize: '0.8rem', fontWeight: '500' }}>
                          {j.error.split('\n')[0].substring(0, 80)}...
                        </div>
                        <button 
                          onClick={() => setSelectedTechJob(j)} 
                          style={{ background: 'none', border: 'none', color: '#93c5fd', fontSize: '0.75rem', cursor: 'pointer', padding: 0, textDecoration: 'underline', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '3px' }}
                        >
                          <Code size={12} /> Inspect Payload & Trace
                        </button>
                      </div>
                    ) : (
                      <button 
                        onClick={() => setSelectedTechJob(j)} 
                        style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '0.75rem', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: '3px' }}
                      >
                        <Code size={12} /> Inspect Payload
                      </button>
                    )}
                  </td>
                  <td style={{ padding: '14px 18px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                    {j.created_at ? new Date(j.created_at.endsWith('Z') ? j.created_at : j.created_at + 'Z').toLocaleTimeString() : '-'}
                  </td>
                  <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                    {(j.status === 'failed' || j.status === 'dead_letter') && (
                      <button onClick={() => handleRetry(j.id)} className="btn btn-primary btn-sm">
                        <RefreshCw size={12} /> Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal Inspector */}
      <Modal
        title={`Job Inspection: ${selectedTechJob?.type}`}
        isOpen={selectedTechJob !== null}
        onClose={() => setSelectedTechJob(null)}
      >
        {selectedTechJob && (
          <div style={{ fontSize: '0.85rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div><strong>Job ID:</strong> <code style={{ fontSize: '0.8rem' }}>{selectedTechJob.id}</code></div>
              <div><strong>Trace ID:</strong> <code style={{ fontSize: '0.8rem' }}>{selectedTechJob.trace_id}</code></div>
              <div><strong>Status:</strong> <Badge status={selectedTechJob.status} /></div>
              <div><strong>Execution Attempts:</strong> {selectedTechJob.attempts} / {selectedTechJob.max_attempts}</div>
            </div>

            {selectedTechJob.payload && (
              <div style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <strong>Stage Payload JSON:</strong>
                  <button 
                    onClick={() => handleCopyPayload(selectedTechJob.payload)}
                    className="btn btn-outline btn-sm"
                    style={{ padding: '2px 8px', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    {copied ? <Check size={12} /> : <Copy size={12} />} Copy JSON
                  </button>
                </div>
                <pre style={{
                  background: 'rgba(0,0,0,0.5)',
                  padding: '12px',
                  borderRadius: '6px',
                  color: '#93c5fd',
                  fontSize: '0.78rem',
                  overflowX: 'auto',
                  maxHeight: '180px',
                  border: '1px solid rgba(255,255,255,0.08)'
                }}>
                  {JSON.stringify(selectedTechJob.payload, null, 2)}
                </pre>
              </div>
            )}

            {selectedTechJob.error && (
              <div style={{ marginTop: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <strong style={{ color: '#fca5a5' }}>Error Traceback / Exception:</strong>
                  <button 
                    onClick={() => handleCopyPayload(selectedTechJob.error)}
                    className="btn btn-outline btn-sm"
                    style={{ padding: '2px 8px', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    {copied ? <Check size={12} /> : <Copy size={12} />} Copy Stack Trace
                  </button>
                </div>
                <pre style={{
                  background: 'rgba(0,0,0,0.5)',
                  padding: '12px',
                  borderRadius: '6px',
                  color: '#fca5a5',
                  fontSize: '0.76rem',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  maxHeight: '200px',
                  border: '1px solid rgba(239,68,68,0.3)'
                }}>
                  {selectedTechJob.error}
                </pre>
              </div>
            )}

            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              {(selectedTechJob.status === 'failed' || selectedTechJob.status === 'dead_letter') && (
                <button 
                  onClick={() => { handleRetry(selectedTechJob.id); setSelectedTechJob(null); }} 
                  className="btn btn-primary btn-sm"
                >
                  <RefreshCw size={14} /> Retry This Job Now
                </button>
              )}
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
};
