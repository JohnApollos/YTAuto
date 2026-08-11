import React, { useState, useMemo } from 'react';
import type { Clip } from '../../types';
import { api, API_BASE } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { FolderCheck, RefreshCw, Search } from 'lucide-react';

interface AssetsViewProps {
  publishedClips: Clip[];
  onRefreshClips: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const AssetsView: React.FC<AssetsViewProps> = ({ publishedClips, onRefreshClips, showToast }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'date_desc' | 'date_asc' | 'duration_desc' | 'duration_asc'>('date_desc');
  const [formatFilter, setFormatFilter] = useState<'all' | 'youtube_clip' | 'reddit_story'>('all');

  const filteredClips = useMemo(() => {
    let list = [...publishedClips];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(c => c.id.toLowerCase().includes(q));
    }

    if (formatFilter === 'reddit_story') {
      list = list.filter(c => c.source_post_id !== null && c.source_post_id !== undefined);
    } else if (formatFilter === 'youtube_clip') {
      list = list.filter(c => c.source_post_id === null || c.source_post_id === undefined);
    }

    list.sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;

      if (sortBy === 'date_desc') return dateB - dateA;
      if (sortBy === 'date_asc') return dateA - dateB;
      if (sortBy === 'duration_desc') return (b.duration_s || 0) - (a.duration_s || 0);
      if (sortBy === 'duration_asc') return (a.duration_s || 0) - (b.duration_s || 0);
      return 0;
    });

    return list;
  }, [publishedClips, searchQuery, sortBy, formatFilter]);

  const handleReExportAll = async () => {
    try {
      showToast('Re-exporting all published clips to C:\\dev\\YTAuto\\exports...', 'info');
      const data = await api.reExportClips();
      showToast(`Re-exported ${data.re_exported_clips} clips!`, 'success');
      onRefreshClips();
    } catch (err: any) {
      showToast(err.message || 'Re-export failed', 'danger');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0 }}>
            <FolderCheck /> Exported Video Assets Library
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Local directory location: <code style={{ color: '#93c5fd' }}>C:\dev\YTAuto\exports\</code>
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleReExportAll}>
          <RefreshCw size={16} /> Sync / Re-export All Files
        </button>
      </div>

      <div className="glass-panel" style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ flex: '1 1 200px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Search size={16} style={{ color: 'var(--text-secondary)' }} />
          <input 
            className="input" 
            placeholder="Search clip ID..." 
            value={searchQuery} 
            onChange={e => setSearchQuery(e.target.value)} 
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Sort By:</label>
          <select className="input" value={sortBy} onChange={e => setSortBy(e.target.value as any)}>
            <option value="date_desc">📅 Newest First</option>
            <option value="date_asc">📅 Oldest First</option>
            <option value="duration_desc">⏱️ Longest First</option>
            <option value="duration_asc">⏱️ Shortest First</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Category:</label>
          <select className="input" value={formatFilter} onChange={e => setFormatFilter(e.target.value as any)}>
            <option value="all">🌐 All Formats ({publishedClips.length})</option>
            <option value="youtube_clip">🎙️ Podcast / YouTube Clips</option>
            <option value="reddit_story">📖 Reddit Story Videos</option>
          </select>
        </div>
      </div>

      {filteredClips.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
          No published video clips found matching your filters.
        </div>
      ) : (
        <div className="grid-cards">
          {filteredClips.map(clip => (
            <div key={clip.id} className="glass-panel" style={{ display: 'flex', flexDirection: 'column', padding: '16px' }}>
              <div style={{ height: '240px', borderRadius: '8px', overflow: 'hidden', backgroundColor: 'black', marginBottom: '14px' }}>
                <video 
                  src={`${API_BASE}/clips/${clip.id}/video`} 
                  controls 
                  preload="metadata"
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h4 style={{ margin: 0, fontSize: '0.95rem' }}>Clip ID: {clip.id.substring(0, 8)}...</h4>
                <Badge status="published" />
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                Format: {clip.source_post_id ? '📖 Reddit Story' : '🎙️ Podcast Clip'}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Duration: {clip.duration_s}s
              </div>
              {clip.created_at && (
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 'auto' }}>
                  Date: {new Date(clip.created_at).toLocaleString()}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
