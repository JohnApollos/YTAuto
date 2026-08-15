import React, { useState } from 'react';
import type { BackgroundAsset } from '../../types';
import { api, API_BASE } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Film, FolderCheck, Play, Shield } from 'lucide-react';

interface BackgroundsViewProps {
  bgAssets: BackgroundAsset[];
  onRefreshBgAssets: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const BackgroundsView: React.FC<BackgroundsViewProps> = ({
  bgAssets,
  onRefreshBgAssets,
  showToast
}) => {
  const [uploading, setUploading] = useState(false);
  const [newBgUrl, setNewBgUrl] = useState('');
  const [previewAsset, setPreviewAsset] = useState<BackgroundAsset | null>(null);

  const handleRegisterUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBgUrl) return;
    try {
      await api.registerBackgroundUrl(newBgUrl.trim());
      showToast('YouTube CC URL registered as background asset!', 'success');
      setNewBgUrl('');
      onRefreshBgAssets();
    } catch (err: any) {
      showToast(err.message || 'Registration failed', 'danger');
    }
  };

  const handleUploadLocalFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadBackgroundFile(file);
      showToast(`Local video file "${file.name}" uploaded successfully!`, 'success');
      onRefreshBgAssets();
    } catch (err: any) {
      showToast(err.message || 'Upload failed', 'danger');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  return (
    <div>
      <h1 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Film /> Background Video Asset Pool
      </h1>
      <p className="text-muted" style={{ marginBottom: '24px' }}>
        Manage background gameplay and ambient video footage used as video backdrops for Reddit story narrations.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
        
        <div className="glass-panel">
          <h3>Option 1: Upload Local Video File (.mp4)</h3>
          <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '16px' }}>
            Select a local `.mp4` video file to upload directly as owned background footage.
          </p>
          <label className="btn btn-primary" style={{ display: 'inline-flex', cursor: 'pointer', gap: '8px' }}>
            <FolderCheck size={16} /> {uploading ? 'Uploading Video File...' : 'Choose Local MP4 File'}
            <input 
              type="file" 
              accept="video/mp4" 
              onChange={handleUploadLocalFile} 
              disabled={uploading} 
              style={{ display: 'none' }} 
            />
          </label>
        </div>

        <div className="glass-panel">
          <h3>Option 2: Register YouTube CC URL</h3>
          <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '16px' }}>
            Enter a YouTube video URL to automatically download Creative Commons background footage.
          </p>
          <form onSubmit={handleRegisterUrl} style={{ display: 'flex', gap: '8px' }}>
            <input 
              className="input" 
              placeholder="YouTube URL (https://www.youtube.com/watch?v=...)" 
              value={newBgUrl} 
              onChange={e => setNewBgUrl(e.target.value)} 
              required 
            />
            <button type="submit" className="btn btn-primary btn-sm">Register URL</button>
          </form>
        </div>

      </div>

      <h3 style={{ marginBottom: '16px' }}>Registered Background Assets ({bgAssets.length})</h3>
      {bgAssets.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '32px' }}>
          No background assets registered yet. Upload an `.mp4` file or register a YouTube URL above!
        </div>
      ) : (
        <div className="grid-cards">
          {bgAssets.map(bg => (
            <div key={bg.id} className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <Badge status={bg.status} />
                  <span style={{ fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '4px', color: '#93c5fd' }}>
                    <Shield size={12} /> {bg.license_type || 'owned'}
                  </span>
                </div>
                <h4 style={{ wordBreak: 'break-all', fontSize: '0.85rem', marginBottom: '10px' }}>{bg.source_url}</h4>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                  {bg.storage_key ? bg.storage_key.substring(0, 16) + '...' : 'No Storage Key'}
                </span>
                {bg.storage_key && (
                  <button 
                    onClick={() => setPreviewAsset(bg)}
                    className="btn btn-outline btn-sm"
                    style={{ padding: '3px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <Play size={12} /> Preview
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Video Preview Modal */}
      <Modal
        title="Background Asset Preview"
        isOpen={previewAsset !== null}
        onClose={() => setPreviewAsset(null)}
      >
        {previewAsset && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{
              width: '100%',
              maxHeight: '400px',
              borderRadius: '8px',
              overflow: 'hidden',
              backgroundColor: '#000',
              marginBottom: '14px'
            }}>
              <video 
                src={`${API_BASE}/background-assets/${previewAsset.id}/file`}
                controls 
                autoPlay 
                style={{ width: '100%', maxHeight: '400px', objectFit: 'contain' }}
              />
            </div>
            <div style={{ fontSize: '0.85rem', width: '100%' }}>
              <div><strong>Source URL:</strong> {previewAsset.source_url}</div>
              <div><strong>License:</strong> {previewAsset.license_type}</div>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
};
