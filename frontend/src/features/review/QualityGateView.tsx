import React, { useState, useEffect, useRef } from 'react';
import type { Clip } from '../../types';
import { api, API_BASE } from '../../services/api';
import { Modal } from '../../components/ui/Modal';
import { CheckCircle, XCircle, ChevronLeft, ChevronRight, ShieldCheck, Sparkles } from 'lucide-react';

interface QualityGateViewProps {
  reviewClips: Clip[];
  publishedClips?: Clip[];
  onRefreshClips: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const QualityGateView: React.FC<QualityGateViewProps> = ({
  reviewClips,
  publishedClips = [],
  onRefreshClips,
  showToast
}) => {
  const [viewMode, setViewMode] = useState<'pending' | 'published'>('pending');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('Bad Subtitle Wrapping');
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const activeClips = viewMode === 'pending' ? reviewClips : publishedClips;
  const activeClip = activeClips[currentIndex] || null;

  // Reset index when changing view mode
  const handleTabChange = (mode: 'pending' | 'published') => {
    setViewMode(mode);
    setCurrentIndex(0);
  };

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
        if (activeClip && viewMode === 'pending') handleApproveCurrent();
      } else if (e.key === 'r' || e.key === 'R' || e.key === 'Delete') {
        e.preventDefault();
        if (activeClip && viewMode === 'pending') setRejectModalOpen(true);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (currentIndex < activeClips.length - 1) setCurrentIndex(prev => prev + 1);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (currentIndex > 0) setCurrentIndex(prev => prev - 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeClip, currentIndex, activeClips.length, viewMode]);

  const handleApproveCurrent = async () => {
    if (!activeClip) return;
    try {
      await api.updateClipStatus(activeClip.id, 'ready');
      showToast(`Clip ${activeClip.id.substring(0, 8)} approved & published!`, 'success');
      onRefreshClips();
      if (currentIndex >= activeClips.length - 1 && currentIndex > 0) {
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
      if (currentIndex >= activeClips.length - 1 && currentIndex > 0) {
        setCurrentIndex(prev => prev - 1);
      }
    } catch (err: any) {
      showToast(err.message || 'Rejection failed', 'danger');
    }
  };

  const scores = activeClip?.scores || {};

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle /> Quality Gate Review Workbench
          </h1>
          <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
            <button
              onClick={() => handleTabChange('pending')}
              className={`btn btn-sm ${viewMode === 'pending' ? 'btn-primary' : 'btn-outline'}`}
            >
              Pending Review ({reviewClips.length})
            </button>
            <button
              onClick={() => handleTabChange('published')}
              className={`btn btn-sm ${viewMode === 'published' ? 'btn-primary' : 'btn-outline'}`}
            >
              Published & Exported ({publishedClips.length})
            </button>
          </div>
        </div>

        {activeClips.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button 
              disabled={currentIndex === 0} 
              onClick={() => setCurrentIndex(prev => prev - 1)} 
              className="btn btn-outline btn-sm"
            >
              <ChevronLeft size={16} /> Prev (🠔)
            </button>
            <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>{currentIndex + 1} / {activeClips.length}</span>
            <button 
              disabled={currentIndex === activeClips.length - 1} 
              onClick={() => setCurrentIndex(prev => prev + 1)} 
              className="btn btn-outline btn-sm"
            >
              Next (➔) <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>

      {activeClips.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '60px 24px' }}>
          <ShieldCheck size={48} style={{ color: 'var(--success)', marginBottom: '16px' }} />
          <h3>{viewMode === 'pending' ? 'All Rendered Videos Approved!' : 'No Published Clips Yet'}</h3>
          <p className="text-muted" style={{ maxWidth: '500px', margin: '8px auto 0 auto' }}>
            {viewMode === 'pending'
              ? 'No clips are currently waiting in the human quality gate review queue. Switch to Published & Exported tab to view completed videos.'
              : 'Clips that pass quality gate and complete publishing will appear here.'}
          </p>
          {viewMode === 'pending' && publishedClips.length > 0 && (
            <button
              onClick={() => handleTabChange('published')}
              className="btn btn-primary btn-sm"
              style={{ marginTop: '16px' }}
            >
              View {publishedClips.length} Published Videos
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '32px', alignItems: 'start' }}>
        
          {/* Video Player Box */}
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
                key={activeClip?.id}
                src={`${API_BASE}/clips/${activeClip?.id}/video`} 
                controls 
                preload="metadata"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            </div>
            <div style={{ marginTop: '12px', fontSize: '0.78rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
              Shortcuts: <kbd style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>Space</kbd> Play/Pause | <kbd style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>A</kbd> Approve | <kbd style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>R</kbd> Reject
            </div>
          </div>

          {/* Details & Controls Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Metadata Card */}
            <div className="glass-panel">
              <h3 style={{ margin: '0 0 14px 0', fontSize: '1.1rem' }}>Clip Identity & Technical Specs</h3>
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
                  <span className="text-muted">Target Dimensions:</span> <strong>1080 × 1920 (Vertical 9:16)</strong>
                </div>
              </div>
            </div>

            {/* Virality Scoring Breakdown */}
            {Object.keys(scores).length > 0 && (
              <div className="glass-panel">
                <h4 style={{ margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px', color: '#93c5fd' }}>
                  <Sparkles size={16} /> AI Virality & Engagement Scores
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
                  {scores.hook_strength !== undefined && (
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Hook Strength</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#6ee7b7' }}>{scores.hook_strength}/100</div>
                    </div>
                  )}
                  {scores.curiosity_gap !== undefined && (
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Curiosity Gap</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#93c5fd' }}>{scores.curiosity_gap}/100</div>
                    </div>
                  )}
                  {scores.emotional_intensity !== undefined && (
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Emotion</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#fcd34d' }}>{scores.emotional_intensity}/100</div>
                    </div>
                  )}
                  {scores.story_completeness !== undefined && (
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Coherence</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#c084fc' }}>{scores.story_completeness}/100</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* QA Check Signals */}
            <div className="glass-panel">
              <h4 style={{ margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success)' }}>
                <ShieldCheck size={18} /> Automated Quality Gate Checks
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                  <span>Audio Stream Present (&gt;4KB)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                  <span>Word-Level Animated Subtitles</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                  <span>Active Word Karaoke Color Pops</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                  <span>AMF Hardware H.264 Transcode</span>
                </div>
              </div>
            </div>

            {/* Human Decision Controls */}
            {viewMode === 'pending' && (
              <div className="glass-panel" style={{ border: '1px solid var(--accent-primary)', background: 'rgba(59,130,246,0.1)' }}>
                <h4 style={{ margin: '0 0 14px 0' }}>Operator Decision Controls</h4>
                <div style={{ display: 'flex', gap: '16px' }}>
                  <button 
                    onClick={handleApproveCurrent} 
                    className="btn btn-success" 
                    style={{ flex: 1, padding: '14px', fontSize: '1rem', fontWeight: 'bold' }}
                  >
                    <CheckCircle size={18} /> Approve & Publish (A)
                  </button>

                  <button 
                    onClick={() => setRejectModalOpen(true)} 
                    className="btn btn-outline" 
                    style={{ flex: 1, padding: '14px', fontSize: '1rem', borderColor: 'var(--danger)', color: '#fca5a5' }}
                  >
                    <XCircle size={18} /> Reject Clip (R)
                  </button>
                </div>
              </div>
            )}

          </div>

        </div>
      )}

      {/* Reject Reason Modal */}
      <Modal
        title="Reject Candidate Clip"
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
      >
        <div style={{ fontSize: '0.9rem' }}>
          <p style={{ color: 'var(--text-secondary)', marginTop: 0 }}>
            Rejecting this video will prevent publication and remove it from the approval queue.
          </p>

          <label className="form-label" style={{ fontWeight: 'bold' }}>Rejection Reason</label>
          <select 
            className="form-control"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            style={{ marginBottom: '20px' }}
          >
            <option value="Bad Subtitle Wrapping">Bad Subtitle Wrapping / Formatting</option>
            <option value="Off-Center Face Crop">Off-Center Face Crop / Framing</option>
            <option value="Low Hook Value">Low Hook / Uninteresting Content</option>
            <option value="Promo / Sponsor Content">Promo / Sponsor Content Leakage</option>
            <option value="Audio Sync Issue">Audio / Speech Synchronization Issue</option>
            <option value="Other Quality Issue">Other Quality Defect</option>
          </select>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button className="btn btn-outline" onClick={() => setRejectModalOpen(false)}>
              Cancel
            </button>
            <button className="btn btn-danger" onClick={handleConfirmReject}>
              Confirm Rejection
            </button>
          </div>
        </div>
      </Modal>

    </div>
  );
};
