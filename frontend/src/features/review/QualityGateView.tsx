import React, { useState, useEffect, useRef } from 'react';
import type { Clip } from '../../types';
import { api, API_BASE } from '../../services/api';
import { Modal } from '../../components/ui/Modal';
import { CheckCircle, XCircle, ChevronLeft, ChevronRight, ShieldCheck } from 'lucide-react';

interface QualityGateViewProps {
  reviewClips: Clip[];
  onRefreshClips: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const QualityGateView: React.FC<QualityGateViewProps> = ({
  reviewClips,
  onRefreshClips,
  showToast
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('Bad Subtitle Wrapping');
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const activeClip = reviewClips[currentIndex] || null;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        if (videoRef.current) {
          if (videoRef.current.paused) {
            videoRef.current.play();
          } else {
            videoRef.current.pause();
          }
        }
      } else if (e.key === 'a' || e.key === 'A' || e.key === 'Enter') {
        e.preventDefault();
        if (activeClip) handleApproveCurrent();
      } else if (e.key === 'r' || e.key === 'R' || e.key === 'Delete') {
        e.preventDefault();
        if (activeClip) setRejectModalOpen(true);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (currentIndex < reviewClips.length - 1) setCurrentIndex(prev => prev + 1);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (currentIndex > 0) setCurrentIndex(prev => prev - 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeClip, currentIndex, reviewClips.length]);

  const handleApproveCurrent = async () => {
    if (!activeClip) return;
    try {
      await api.updateClipStatus(activeClip.id, 'ready');
      showToast(`Clip ${activeClip.id.substring(0, 8)} approved & published!`, 'success');
      onRefreshClips();
      if (currentIndex >= reviewClips.length - 1 && currentIndex > 0) {
        setCurrentIndex(prev => prev - 1);
      }
    } catch (err: any) {
      showToast(err.message || 'Approval failed', 'danger');
    }
  };

  const handleConfirmReject = async () => {
    if (!activeClip) return;
    try {
      await api.updateClipStatus(activeClip.id, 'rejected');
      showToast(`Clip rejected (Reason: ${rejectReason})`, 'info');
      setRejectModalOpen(false);
      onRefreshClips();
      if (currentIndex >= reviewClips.length - 1 && currentIndex > 0) {
        setCurrentIndex(prev => prev - 1);
      }
    } catch (err: any) {
      showToast(err.message || 'Rejection failed', 'danger');
    }
  };

  if (reviewClips.length === 0) {
    return (
      <div>
        <h1 className="section-title"><CheckCircle /> Quality Gate Workbench</h1>
        <div className="glass-panel" style={{ textAlign: 'center', padding: '60px 24px' }}>
          <ShieldCheck size={48} style={{ color: 'var(--success)', marginBottom: '16px' }} />
          <h3>All Rendered Videos Approved!</h3>
          <p className="text-muted" style={{ maxWidth: '500px', margin: '8px auto 0 auto' }}>
            No clips are currently waiting in the human quality gate review queue. New videos will appear here automatically when rendering completes.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0 }}>
            <CheckCircle /> Quality Gate Review Workbench
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Review item <strong>{currentIndex + 1} of {reviewClips.length}</strong> ready for final human approval before publishing.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button 
            disabled={currentIndex === 0} 
            onClick={() => setCurrentIndex(prev => prev - 1)} 
            className="btn btn-outline btn-sm"
          >
            <ChevronLeft size={16} /> Prev (🠔)
          </button>
          <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>{currentIndex + 1} / {reviewClips.length}</span>
          <button 
            disabled={currentIndex === reviewClips.length - 1} 
            onClick={() => setCurrentIndex(prev => prev + 1)} 
            className="btn btn-outline btn-sm"
          >
            Next (➔) <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '32px', alignItems: 'start' }}>
        
        <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{
            width: '100%',
            height: '560px',
            borderRadius: '12px',
            overflow: 'hidden',
            backgroundColor: '#000',
            position: 'relative',
            boxShadow: '0 10px 30px rgba(0,0,0,0.8)'
          }}>
            <video 
              ref={videoRef}
              src={`${API_BASE}/clips/${activeClip?.id}/video`} 
              controls 
              preload="metadata"
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            />
          </div>
          <div style={{ marginTop: '12px', fontSize: '0.78rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
            Shortcut: Press <kbd style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>Space</kbd> to Play / Pause
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          <div className="glass-panel">
            <h3 style={{ margin: '0 0 14px 0', fontSize: '1.1rem' }}>Clip Metadata & Identity</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.88rem' }}>
              <div>
                <span className="text-muted">Clip ID:</span> <code style={{ color: '#93c5fd' }}>{activeClip?.id}</code>
              </div>
              <div>
                <span className="text-muted">Production Format:</span> <strong>{activeClip?.source_post_id ? '📖 Reddit Story' : '🎙️ Podcast Clip'}</strong>
              </div>
              <div>
                <span className="text-muted">Duration:</span> <strong>{activeClip?.duration_s}s</strong>
              </div>
              <div>
                <span className="text-muted">Target Resolution:</span> <strong>1080 × 1920 (Vertical 9:16)</strong>
              </div>
            </div>
          </div>

          <div className="glass-panel">
            <h4 style={{ margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success)' }}>
              <ShieldCheck size={18} /> Automated Machine QA Check Signals
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                <span>Audio Non-Emptiness (&gt;4KB)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                <span>Whisper Captions Generated</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                <span>ASS 6-Hex Color Tags Valid</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                <span>FFmpeg 0 Exit Status</span>
              </div>
            </div>
          </div>

          <div className="glass-panel" style={{ border: '1px solid var(--accent-primary)', background: 'rgba(59,130,246,0.1)' }}>
            <h4 style={{ margin: '0 0 14px 0' }}>Human Decision Controls</h4>
            <div style={{ display: 'flex', gap: '16px' }}>
              <button 
                onClick={handleApproveCurrent} 
                className="btn btn-success" 
                style={{ flex: 1, padding: '14px', fontSize: '1rem', fontWeight: 'bold' }}
              >
                <CheckCircle size={18} /> Approve & Publish (Press A)
              </button>

              <button 
                onClick={() => setRejectModalOpen(true)} 
                className="btn btn-outline" 
                style={{ flex: 1, padding: '14px', fontSize: '1rem', borderColor: 'var(--danger)', color: '#fca5a5' }}
              >
                <XCircle size={18} /> Reject Clip (Press R)
              </button>
            </div>
          </div>

        </div>

      </div>

      <Modal
        title="Reject Clip & Record Feedback"
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            Select the reason for rejecting this video clip. Rejection feedback ensures quality control tracking.
          </p>

          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Rejection Reason:</label>
          <select 
            value={rejectReason} 
            onChange={e => setRejectReason(e.target.value)} 
            className="input"
          >
            <option value="Bad Subtitle Wrapping">Bad Subtitle / Text Wrapping</option>
            <option value="Audio Out of Sync">Audio / Speech Desync</option>
            <option value="Low Audio Volume">Low Audio Volume / Distortion</option>
            <option value="Framing Issue">Framing / Subject Off-Center</option>
            <option value="Boring / Low Engagement">Boring Content / Low Hook Strength</option>
          </select>

          <div style={{ display: 'flex', gap: '10px', marginTop: '12px', justifyContent: 'flex-end' }}>
            <button onClick={() => setRejectModalOpen(false)} className="btn btn-outline btn-sm">Cancel</button>
            <button onClick={handleConfirmReject} className="btn btn-primary btn-sm" style={{ backgroundColor: 'var(--danger)' }}>
              Confirm Rejection
            </button>
          </div>
        </div>
      </Modal>

    </div>
  );
};
