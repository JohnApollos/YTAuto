import React, { useState } from 'react';
import type { Channel, ContentSource } from '../../types';
import { api } from '../../services/api';
import { Settings, Play, Pause } from 'lucide-react';

interface SourcesViewProps {
  channels: Channel[];
  selectedChannelId: string;
  onSelectChannelId: (id: string) => void;
  sources: ContentSource[];
  onRefreshChannels: () => void;
  onRefreshSources: (channelId: string) => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const SourcesView: React.FC<SourcesViewProps> = ({
  channels,
  selectedChannelId,
  onSelectChannelId,
  sources,
  onRefreshChannels,
  onRefreshSources,
  showToast
}) => {
  const [newChannel, setNewChannel] = useState({
    name: '',
    slug: '',
    niche: 'Reddit Stories',
    project_id: 'default_project',
    language: 'en'
  });

  const [newSource, setNewSource] = useState({
    type: 'youtube_channel',
    external_ref: '',
    poll_interval_minutes: 60,
    max_new_videos_per_poll: 1
  });

  const handleAddChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChannel.name || !newChannel.slug) {
      showToast('Channel Name and Slug are required', 'danger');
      return;
    }
    try {
      const created = await api.createChannel({
        name: newChannel.name.trim(),
        slug: newChannel.slug.trim(),
        niche: newChannel.niche,
        project_id: newChannel.project_id,
        language: newChannel.language
      });
      showToast(`Channel "${created.name}" created successfully!`, 'success');
      setNewChannel({ name: '', slug: '', niche: 'Reddit Stories', project_id: 'default_project', language: 'en' });
      onRefreshChannels();
      onSelectChannelId(created.id);
    } catch (err: any) {
      showToast(err.message || 'Failed to create channel', 'danger');
    }
  };

  const handleAddSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChannelId) {
      showToast('Please select a channel first', 'danger');
      return;
    }
    if (!newSource.external_ref) {
      showToast('External Ref (Channel ID or Name) is required', 'danger');
      return;
    }
    try {
      await api.createSource({
        channel_id: selectedChannelId,
        type: newSource.type,
        external_ref: newSource.external_ref.trim(),
        config: {
          poll_interval_minutes: Number(newSource.poll_interval_minutes),
          max_new_videos_per_poll: Number(newSource.max_new_videos_per_poll)
        }
      });
      showToast('Content Source added successfully!', 'success');
      setNewSource({ type: 'youtube_channel', external_ref: '', poll_interval_minutes: 60, max_new_videos_per_poll: 1 });
      onRefreshSources(selectedChannelId);
    } catch (err: any) {
      showToast(err.message || 'Failed to add source', 'danger');
    }
  };

  const handleToggleActive = async (sourceId: string, currentActive: boolean) => {
    try {
      await api.updateSourceActive(sourceId, !currentActive);
      showToast(`Source ${!currentActive ? 'activated' : 'paused'}`, 'success');
      onRefreshSources(selectedChannelId);
    } catch (err: any) {
      showToast(err.message || 'Failed to update source status', 'danger');
    }
  };

  return (
    <div>
      <h1 className="section-title"><Settings /> Channels & Content Sources Manager</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
        
        <div className="glass-panel">
          <h3>Channel Profiles</h3>
          <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '16px' }}>
            Register target YouTube channel profiles for content distribution.
          </p>

          <form onSubmit={handleAddChannel} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input className="input" placeholder="Channel Name" value={newChannel.name} onChange={e => setNewChannel({ ...newChannel, name: e.target.value })} required />
            <input className="input" placeholder="Slug (e.g. reddit_narrations)" value={newChannel.slug} onChange={e => setNewChannel({ ...newChannel, slug: e.target.value })} required />
            <input className="input" placeholder="Niche (e.g. Reddit Stories)" value={newChannel.niche} onChange={e => setNewChannel({ ...newChannel, niche: e.target.value })} />
            <button type="submit" className="btn btn-primary">Add Channel Profile</button>
          </form>
        </div>

        <div className="glass-panel">
          <h3>Configured Content Sources</h3>
          
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Select Active Channel:</label>
            <select value={selectedChannelId} onChange={e => onSelectChannelId(e.target.value)} className="input">
              <option value="">-- Select Channel --</option>
              {channels.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.slug})</option>
              ))}
            </select>
          </div>

          <form onSubmit={handleAddSource} style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px', padding: '14px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
            <h4 style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Add New Source</h4>
            <select className="input" value={newSource.type} onChange={e => setNewSource({ ...newSource, type: e.target.value })}>
              <option value="youtube_channel">YouTube Channel</option>
              <option value="curated_story">Curated Reddit Story</option>
            </select>
            <input className="input" placeholder="External Ref (Channel ID / Name)" value={newSource.external_ref} onChange={e => setNewSource({ ...newSource, external_ref: e.target.value })} required />
            <button type="submit" className="btn btn-primary btn-sm">Add Content Source</button>
          </form>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {sources.map(s => (
              <div key={s.id} style={{ padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 'bold' }}>{s.external_ref}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Type: {s.type} | Max per poll: {s.config?.max_new_videos_per_poll || 1}
                  </div>
                </div>
                <button onClick={() => handleToggleActive(s.id, s.active)} className={`btn btn-sm ${s.active ? 'btn-outline' : 'btn-primary'}`}>
                  {s.active ? <Pause size={12} /> : <Play size={12} />} {s.active ? 'Pause' : 'Activate'}
                </button>
              </div>
            ))}
          </div>

        </div>

      </div>
    </div>
  );
};
