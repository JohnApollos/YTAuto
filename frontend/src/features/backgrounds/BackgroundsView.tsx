import React, { useState } from 'react';
import type { BackgroundAsset } from '../../types';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { Film, FolderCheck } from 'lucide-react';

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
      <h1 className="section-title"><Film /> Background Video Asset Pool</h1>
      <p className="text-muted" style={{ marginBottom: '24px' }}>
        Manage background gameplay or ambient video footage used as video backdrops for Reddit story narrations.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
        
        <div className="glass-panel">
          <h3>Option 1: Upload Local Video File (.mp4)</h3>
          <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '16px' }}>
            Select a local `.mp4` video file to upload directly as owned background footage.
          </p>
          <label className="btn btn-primary" style={{ display: 'inline-flex', cursor: 'pointer' }}>
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
            <div key={bg.id} className="glass-panel">
              <h4 style={{ wordBreak: 'break-all', fontSize: '0.85rem', marginBottom: '10px' }}>{bg.source_url}</h4>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Badge status={bg.status} />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Storage Key: {bg.storage_key?.substring(0, 16)}...
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
