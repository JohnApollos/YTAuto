import React, { useState } from 'react';
import type { Job } from '../../types';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Activity, RefreshCw, Code } from 'lucide-react';

interface JobsViewProps {
  jobs: Job[];
  onRefreshJobs: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const JobsView: React.FC<JobsViewProps> = ({ jobs, onRefreshJobs, showToast }) => {
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedTechJob, setSelectedTechJob] = useState<Job | null>(null);

  const filteredJobs = statusFilter === 'all' 
    ? jobs 
    : jobs.filter(j => j.status === statusFilter);

  const handleRetry = async (jobId: string) => {
    try {
      await api.retryJob(jobId);
      showToast('Job re-queued successfully!', 'success');
      onRefreshJobs();
    } catch (err: any) {
      showToast(err.message || 'Failed to retry job', 'danger');
    }
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0 }}>
            <Activity /> Production Queue & Execution Monitor
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Real-time visibility into all autonomous pipeline background jobs and execution attempts.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-outline" onClick={handleFlushStuck}>
            <RefreshCw size={16} /> Flush Stuck Jobs
          </button>
          <button className="btn btn-primary" onClick={onRefreshJobs}>
            <RefreshCw size={16} /> Refresh Queue
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', flexWrap: 'wrap' }}>
        {['all', 'queued', 'running', 'succeeded', 'failed', 'dead_letter', 'cancelled'].map(st => {
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

      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        {filteredJobs.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            No background jobs found for status filter "{statusFilter}".
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.05)', borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '14px 18px' }}>Pipeline Stage & Trace ID</th>
                <th style={{ padding: '14px 18px' }}>Status</th>
                <th style={{ padding: '14px 18px' }}>Attempts</th>
                <th style={{ padding: '14px 18px' }}>Operator Summary</th>
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
                          <Code size={12} /> View Technical Details
                        </button>
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Operational</span>
                    )}
                  </td>
                  <td style={{ padding: '14px 18px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                    {j.created_at ? new Date(j.created_at.endsWith('Z') ? j.created_at : j.created_at + 'Z').toLocaleString() : '-'}
                  </td>
                  <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                    {(j.status === 'failed' || j.status === 'dead_letter') && (
                      <button onClick={() => handleRetry(j.id)} className="btn btn-primary btn-sm">
                        <RefreshCw size={12} /> Retry Job
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        title={`Technical Job Details: ${selectedTechJob?.type}`}
        isOpen={selectedTechJob !== null}
        onClose={() => setSelectedTechJob(null)}
      >
        {selectedTechJob && (
          <div style={{ fontSize: '0.85rem' }}>
            <div style={{ marginBottom: '12px' }}>
              <strong>Trace ID:</strong> <code>{selectedTechJob.trace_id}</code>
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>Attempts:</strong> {selectedTechJob.attempts} / {selectedTechJob.max_attempts}
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>Status:</strong> <Badge status={selectedTechJob.status} />
            </div>
            <div style={{ marginTop: '16px' }}>
              <strong>Raw Error Traceback / Stack:</strong>
              <pre style={{
                background: 'rgba(0,0,0,0.5)',
                padding: '14px',
                borderRadius: '8px',
                color: '#fca5a5',
                fontSize: '0.78rem',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                marginTop: '6px',
                border: '1px solid rgba(239,68,68,0.3)'
              }}>
                {selectedTechJob.error || 'No stack trace available.'}
              </pre>
            </div>
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button 
                onClick={() => { handleRetry(selectedTechJob.id); setSelectedTechJob(null); }} 
                className="btn btn-primary btn-sm"
              >
                <RefreshCw size={14} /> Retry This Job Now
              </button>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
};
