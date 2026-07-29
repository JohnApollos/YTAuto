import { useState, useEffect } from 'react';
import { Activity, Video, LayoutDashboard, Settings, RefreshCw, Check, X, Shield, Key, Database } from 'lucide-react';
import './index.css';

const API_BASE = window.location.origin.includes('5173') || window.location.origin.includes('3000')
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

interface Channel {
  id: string;
  name: string;
  slug: string;
  niche: string;
  status: string;
  project_id: string;
  language: string;
}

interface ContentSource {
  id: string;
  channel_id: string;
  type: string;
  external_ref: string;
  active: boolean;
  last_polled_at: string | null;
  config: any;
}

interface Clip {
  id: string;
  channel_id: string;
  status: string;
  duration_s: number;
  created_at: string | null;
  scores: any;
}

interface Quota {
  project_id: string;
  remaining: number;
  error?: string;
}

interface ModelHealth {
  healthy: boolean;
  model_name: string;
  message: string;
}

function App() {
  const [activeTab, setActiveTab] = useState('setup');
  
  // Channels
  const [channels, setChannels] = useState<Channel[]>([]);
  const [newChannel, setNewChannel] = useState({
    name: '',
    slug: '',
    niche: '',
    project_id: 'default_project',
    youtube_api_key: '',
    language: 'en'
  });
  
  // Content Sources
  const [selectedChannelId, setSelectedChannelId] = useState('');
  const [sources, setSources] = useState<ContentSource[]>([]);
  const [newSource, setNewSource] = useState({
    external_ref: '',
    poll_interval_minutes: 60
  });

  // Rights & OAuth
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [rightsStatus, setRightsStatus] = useState('unknown');
  const [evidenceRef, setEvidenceRef] = useState('');
  const [oauthChannelId, setOauthChannelId] = useState('');
  const [oauthCreds, setOauthCreds] = useState({
    token: '',
    refresh_token: '',
    client_id: '',
    client_secret: ''
  });

  // Pipeline/Health/Quotas
  const [health, setHealth] = useState<any>(null);
  const [models, setModels] = useState<Record<string, ModelHealth>>({});
  const [quotas, setQuotas] = useState<Quota[]>([]);
  const [healthLoading, setHealthLoading] = useState(false);

  // Review Clips & Assets
  const [reviewClips, setReviewClips] = useState<Clip[]>([]);
  const [publishedClips, setPublishedClips] = useState<Clip[]>([]);
  
  // Status/Messages
  const [message, setMessage] = useState({ text: '', type: '' });

  const showMessage = (text: string, type: 'success' | 'danger' | 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: '', type: '' }), 5000);
  };

  // Fetch functions
  const fetchChannels = async () => {
    try {
      const res = await fetch(`${API_BASE}/channels/`);
      const data = await res.json();
      setChannels(data.channels || []);
      if (data.channels && data.channels.length > 0 && !selectedChannelId) {
        setSelectedChannelId(data.channels[0].id);
        setOauthChannelId(data.channels[0].id);
      }
    } catch (err: any) {
      console.error('Failed to fetch channels:', err);
    }
  };

  const fetchSources = async (channelId: string) => {
    if (!channelId) return;
    try {
      const res = await fetch(`${API_BASE}/sources/?channel_id=${channelId}`);
      const data = await res.json();
      setSources(data.sources || []);
      if (data.sources && data.sources.length > 0) {
        setSelectedSourceId(data.sources[0].id);
      } else {
        setSelectedSourceId('');
      }
    } catch (err: any) {
      console.error('Failed to fetch sources:', err);
    }
  };

  const fetchRightsStatus = async (sourceId: string) => {
    if (!sourceId) return;
    try {
      const res = await fetch(`${API_BASE}/rights/${sourceId}`);
      const data = await res.json();
      setRightsStatus(data.status || 'unknown');
      setEvidenceRef(data.evidence_ref || '');
    } catch (err) {
      console.error('Failed to fetch rights:', err);
    }
  };

  const fetchSystemData = async () => {
    setHealthLoading(true);
    try {
      const [hRes, mRes, qRes] = await Promise.all([
        fetch(`${API_BASE}/system/health`),
        fetch(`${API_BASE}/system/models`),
        fetch(`${API_BASE}/system/quota`)
      ]);
      setHealth(await hRes.json());
      const modelData = await mRes.json();
      setModels(modelData.models || {});
      const quotaData = await qRes.json();
      setQuotas(quotaData.quotas || []);
    } catch (err) {
      console.error('Failed to fetch system data:', err);
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchClips = async () => {
    try {
      const [passedRes, pubRes] = await Promise.all([
        fetch(`${API_BASE}/clips/?status=qc_passed`),
        // Also list 'ready' clips for review just in case, but target says qc_passed
        fetch(`${API_BASE}/clips/?status=published`)
      ]);
      const passedData = await passedRes.json();
      setReviewClips(passedData.clips || []);
      const pubData = await pubRes.json();
      setPublishedClips(pubData.clips || []);
    } catch (err) {
      console.error('Failed to fetch clips:', err);
    }
  };

  // Trigger loads on tab change
  useEffect(() => {
    fetchChannels();
    if (activeTab === 'overview') {
      fetchSystemData();
    } else if (activeTab === 'candidates' || activeTab === 'assets') {
      fetchClips();
    }
  }, [activeTab]);

  useEffect(() => {
    if (selectedChannelId) {
      fetchSources(selectedChannelId);
    }
  }, [selectedChannelId]);

  useEffect(() => {
    if (selectedSourceId) {
      fetchRightsStatus(selectedSourceId);
    } else {
      setRightsStatus('unknown');
      setEvidenceRef('');
    }
  }, [selectedSourceId]);

  // Submits
  const handleAddChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChannel.name || !newChannel.slug) {
      showMessage('Name and Slug are required', 'danger');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/channels/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newChannel.name,
          slug: newChannel.slug,
          niche: newChannel.niche,
          project_id: newChannel.project_id,
          language: newChannel.language
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create channel');
      }
      
      const created = await res.json();
      // If API key was provided, we auto-create a source config or use it
      showMessage(`Channel "${created.name}" created successfully!`, 'success');
      setNewChannel({
        name: '',
        slug: '',
        niche: '',
        project_id: 'default_project',
        youtube_api_key: '',
        language: 'en'
      });
      fetchChannels();
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleAddSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChannelId) {
      showMessage('Please select or create a channel first', 'danger');
      return;
    }
    if (!newSource.external_ref) {
      showMessage('YouTube Channel ID is required', 'danger');
      return;
    }
    try {
      // Find the channel's API key if entered in form
      const apiKey = newChannel.youtube_api_key || undefined;
      const res = await fetch(`${API_BASE}/sources/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel_id: selectedChannelId,
          type: 'youtube_channel',
          external_ref: newSource.external_ref,
          config: {
            api_key: apiKey,
            poll_interval_minutes: Number(newSource.poll_interval_minutes)
          }
        })
      });
      if (!res.ok) throw new Error('Failed to add source');
      showMessage('YouTube source added successfully!', 'success');
      setNewSource({ external_ref: '', poll_interval_minutes: 60 });
      fetchSources(selectedChannelId);
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleSaveRights = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSourceId) {
      showMessage('Please select a content source', 'danger');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/rights/${selectedSourceId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: rightsStatus,
          evidence_ref: evidenceRef || null,
          reviewed_by: 'operator'
        })
      });
      if (!res.ok) throw new Error('Failed to update rights');
      showMessage('Rights status updated successfully!', 'success');
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleSaveOAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oauthChannelId) {
      showMessage('Please select a channel', 'danger');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/channels/${oauthChannelId}/oauth`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(oauthCreds)
      });
      if (!res.ok) throw new Error('Failed to save OAuth credentials');
      showMessage('OAuth credentials saved successfully!', 'success');
      setOauthCreds({ token: '', refresh_token: '', client_id: '', client_secret: '' });
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleClipAction = async (clipId: string, approve: boolean) => {
    try {
      const status = approve ? 'ready' : 'qc_failed';
      const res = await fetch(`${API_BASE}/clips/${clipId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      if (!res.ok) throw new Error('Failed to process clip');
      showMessage(approve ? 'Clip approved for publishing!' : 'Clip rejected.', approve ? 'success' : 'info');
      fetchClips();
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
          <div className="status-indicator"></div>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Autonomous Media</h2>
        </div>
        
        <button 
          className={`btn ${activeTab === 'setup' ? 'btn-primary' : 'glass-panel'}`}
          onClick={() => setActiveTab('setup')}
          style={{ justifyContent: 'flex-start', padding: '12px 16px', border: 'none' }}
        >
          <Settings size={18} /> Setup Control
        </button>

        <button 
          className={`btn ${activeTab === 'overview' ? 'btn-primary' : 'glass-panel'}`}
          onClick={() => setActiveTab('overview')}
          style={{ justifyContent: 'flex-start', padding: '12px 16px', border: 'none' }}
        >
          <LayoutDashboard size={18} /> Pipeline Overview
        </button>
        
        <button 
          className={`btn ${activeTab === 'candidates' ? 'btn-primary' : 'glass-panel'}`}
          onClick={() => setActiveTab('candidates')}
          style={{ justifyContent: 'flex-start', padding: '12px 16px', border: 'none' }}
        >
          <Activity size={18} /> Candidate Review
        </button>
        
        <button 
          className={`btn ${activeTab === 'assets' ? 'btn-primary' : 'glass-panel'}`}
          onClick={() => setActiveTab('assets')}
          style={{ justifyContent: 'flex-start', padding: '12px 16px', border: 'none' }}
        >
          <Video size={18} /> Asset Library
        </button>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {/* Global Toast Alert */}
        {message.text && (
          <div className={`glass-panel badge-${message.type}`} style={{ 
            position: 'fixed', 
            top: '20px', 
            right: '20px', 
            zIndex: 1000, 
            padding: '16px 24px', 
            borderRadius: '12px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            textTransform: 'none'
          }}>
            {message.text}
          </div>
        )}

        {/* TAB 1: SETUP */}
        {activeTab === 'setup' && (
          <div>
            <h1 className="section-title"><Settings /> System Setup Control</h1>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
              {/* Section A: Channels */}
              <div className="glass-panel">
                <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}><Database size={20} /> Section A: Manage Channels</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                  {/* Channels List */}
                  <div>
                    <h4 className="text-muted">Registered Channels</h4>
                    {channels.length === 0 ? (
                      <p style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>No channels registered yet. Add one on the right.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '300px', overflowY: 'auto' }}>
                        {channels.map(c => (
                          <div key={c.id} style={{ padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                            <div style={{ fontWeight: 'bold' }}>{c.name} <span className="badge badge-active" style={{ fontSize: '0.65rem', verticalAlign: 'middle' }}>{c.status}</span></div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Slug: {c.slug} | Project: {c.project_id}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  {/* Add Channel Form */}
                  <form onSubmit={handleAddChannel} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h4 className="text-muted">Register New Channel</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <input 
                        type="text" 
                        placeholder="Channel Name" 
                        value={newChannel.name}
                        onChange={e => setNewChannel({...newChannel, name: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                      <input 
                        type="text" 
                        placeholder="slug-name" 
                        value={newChannel.slug}
                        onChange={e => setNewChannel({...newChannel, slug: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <input 
                        type="text" 
                        placeholder="Niche (e.g. Podcasts)" 
                        value={newChannel.niche}
                        onChange={e => setNewChannel({...newChannel, niche: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                      <input 
                        type="text" 
                        placeholder="GCP Project ID" 
                        value={newChannel.project_id}
                        onChange={e => setNewChannel({...newChannel, project_id: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <input 
                        type="password" 
                        placeholder="YouTube API Key (Optional)" 
                        value={newChannel.youtube_api_key}
                        onChange={e => setNewChannel({...newChannel, youtube_api_key: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                      <select 
                        value={newChannel.language}
                        onChange={e => setNewChannel({...newChannel, language: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(15,23,42,0.9)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      >
                        <option value="en">English (en)</option>
                        <option value="es">Spanish (es)</option>
                        <option value="pt">Portuguese (pt)</option>
                      </select>
                    </div>
                    <button type="submit" className="btn btn-primary">Add Channel</button>
                  </form>
                </div>
              </div>

              {/* Section B: Content Sources */}
              <div className="glass-panel">
                <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}><Video size={20} /> Section B: Content Sources</h3>
                
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Select Channel to configure Sources:</label>
                  <select 
                    value={selectedChannelId} 
                    onChange={e => setSelectedChannelId(e.target.value)}
                    style={{ padding: '10px', background: 'rgba(15,23,42,0.9)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px', width: '300px' }}
                  >
                    <option value="">-- Select Channel --</option>
                    {channels.map(c => (
                      <option key={c.id} value={c.id}>{c.name} ({c.slug})</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                  <div>
                    <h4 className="text-muted">Sources for Channel</h4>
                    {sources.length === 0 ? (
                      <p style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>No sources configured for this channel.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {sources.map(s => (
                          <div key={s.id} style={{ padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontWeight: 'bold' }}>{s.external_ref}</div>
                              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Type: {s.type} | Active: {s.active ? 'Yes' : 'No'}</div>
                            </div>
                            <span className={`badge ${s.active ? 'badge-completed' : 'badge-pending'}`}>{s.active ? 'active' : 'paused'}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <form onSubmit={handleAddSource} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h4 className="text-muted">Add YouTube Source Channel</h4>
                    <input 
                      type="text" 
                      placeholder="YouTube Channel ID (e.g. UCxxxxxxxxxxxxx)" 
                      value={newSource.external_ref}
                      onChange={e => setNewSource({...newSource, external_ref: e.target.value})}
                      style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    />
                    <input 
                      type="number" 
                      placeholder="Poll Interval (Minutes)" 
                      value={newSource.poll_interval_minutes}
                      onChange={e => setNewSource({...newSource, poll_interval_minutes: Number(e.target.value)})}
                      style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    />
                    <button type="submit" className="btn btn-primary">Add Source</button>
                  </form>
                </div>
              </div>

              {/* Section C: Rights & OAuth */}
              <div className="glass-panel">
                <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}><Shield size={20} /> Section C: Rights & OAuth Credentials</h3>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                  {/* Rights Form */}
                  <form onSubmit={handleSaveRights} style={{ display: 'flex', flexDirection: 'column', gap: '12px', borderRight: '1px solid var(--border-color)', paddingRight: '32px' }}>
                    <h4 className="text-muted"><Shield size={16} /> Content Rights Clearance</h4>
                    
                    <label style={{ color: 'var(--text-secondary)' }}>Select Content Source:</label>
                    <select 
                      value={selectedSourceId} 
                      onChange={e => setSelectedSourceId(e.target.value)}
                      style={{ padding: '10px', background: 'rgba(15,23,42,0.9)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    >
                      <option value="">-- Select Source --</option>
                      {sources.map(s => (
                        <option key={s.id} value={s.id}>{s.external_ref} ({s.type})</option>
                      ))}
                    </select>

                    <label style={{ color: 'var(--text-secondary)' }}>Rights Status:</label>
                    <select 
                      value={rightsStatus} 
                      onChange={e => setRightsStatus(e.target.value)}
                      style={{ padding: '10px', background: 'rgba(15,23,42,0.9)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    >
                      <option value="unknown">Unknown (Blocked)</option>
                      <option value="owned">Owned (Cleared)</option>
                      <option value="licensed">Licensed (Cleared)</option>
                      <option value="permission_granted">Permission Granted (Cleared)</option>
                      <option value="denied">Denied (Blocked)</option>
                    </select>

                    <input 
                      type="text" 
                      placeholder="Evidence URL / Ref" 
                      value={evidenceRef}
                      onChange={e => setEvidenceRef(e.target.value)}
                      style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    />
                    
                    <button type="submit" className="btn btn-success" style={{ marginTop: '8px' }}>Save Rights Clearance</button>
                  </form>

                  {/* YouTube OAuth Form */}
                  <form onSubmit={handleSaveOAuth} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h4 className="text-muted"><Key size={16} /> YouTube OAuth Credentials</h4>
                    
                    <label style={{ color: 'var(--text-secondary)' }}>Select Target Channel:</label>
                    <select 
                      value={oauthChannelId} 
                      onChange={e => setOauthChannelId(e.target.value)}
                      style={{ padding: '10px', background: 'rgba(15,23,42,0.9)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    >
                      <option value="">-- Select Channel --</option>
                      {channels.map(c => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <input 
                        type="password" 
                        placeholder="OAuth Access Token" 
                        value={oauthCreds.token}
                        onChange={e => setOauthCreds({...oauthCreds, token: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                      <input 
                        type="password" 
                        placeholder="OAuth Refresh Token" 
                        value={oauthCreds.refresh_token}
                        onChange={e => setOauthCreds({...oauthCreds, refresh_token: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <input 
                        type="password" 
                        placeholder="OAuth Client ID" 
                        value={oauthCreds.client_id}
                        onChange={e => setOauthCreds({...oauthCreds, client_id: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                      <input 
                        type="password" 
                        placeholder="OAuth Client Secret" 
                        value={oauthCreds.client_secret}
                        onChange={e => setOauthCreds({...oauthCreds, client_secret: e.target.value})}
                        style={{ padding: '10px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      />
                    </div>

                    <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      Note: You must obtain OAuth tokens by running the authentication consent flow against GCP client credentials.
                    </p>
                    
                    <button type="submit" className="btn btn-primary">Save OAuth Credentials</button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: OVERVIEW */}
        {activeTab === 'overview' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h1 className="section-title" style={{ margin: 0 }}><LayoutDashboard /> Pipeline Overview</h1>
              <button onClick={fetchSystemData} disabled={healthLoading} className="btn glass-panel" style={{ padding: '8px 12px' }}>
                <RefreshCw size={14} className={healthLoading ? 'spin' : ''} /> Refresh Status
              </button>
            </div>

            {/* Health indicators */}
            <div className="grid-cards" style={{ marginBottom: '32px' }}>
              <div className="glass-panel">
                <h4>System Health Status</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Database:</span>
                    <span className={`badge ${health?.db === 'ok' ? 'badge-completed' : 'badge-pending'}`}>{health?.db || 'unknown'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Redis:</span>
                    <span className={`badge ${health?.redis === 'ok' ? 'badge-completed' : 'badge-pending'}`}>{health?.redis || 'unknown'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>MinIO Object Storage:</span>
                    <span className={`badge ${health?.minio === 'ok' ? 'badge-completed' : 'badge-pending'}`}>{health?.minio || 'unknown'}</span>
                  </div>
                </div>
              </div>

              {/* Upload Quotas */}
              <div className="glass-panel">
                <h4>YouTube Quota Pools (1600 units/publish)</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                  {quotas.length === 0 ? (
                    <div style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>No active quotas found.</div>
                  ) : (
                    quotas.map(q => (
                      <div key={q.project_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.85rem' }}>{q.project_id}:</span>
                        <span style={{ fontWeight: 'bold' }} className={q.remaining < 1600 ? 'badge-pending' : 'badge-completed'}>
                          {q.remaining} units remaining
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Model Runtimes */}
            <div className="glass-panel" style={{ marginBottom: '32px' }}>
              <h3><Database size={20} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Model Runtime Services</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '20px', marginTop: '16px' }}>
                {Object.keys(models).length === 0 ? (
                  <p style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>No active models registered.</p>
                ) : (
                  Object.entries(models).map(([stage, info]) => (
                    <div key={stage} style={{ padding: '16px', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                      <div style={{ fontWeight: 'bold', textTransform: 'capitalize' }}>{stage}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '4px 0 12px 0' }}>Model: {info.model_name}</div>
                      <span className={`badge ${info.healthy ? 'badge-completed' : 'badge-pending'}`}>
                        {info.healthy ? 'online' : 'offline'}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CANDIDATE REVIEW */}
        {activeTab === 'candidates' && (
          <div>
            <h1 className="section-title"><Activity /> Candidate Review (Manual Override)</h1>
            <p className="text-muted" style={{ marginBottom: '24px' }}>
              Review vertical video clips that passed automated QC gates. Approve to publish or reject to discard.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {reviewClips.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                  <Check size={48} style={{ marginBottom: '16px', color: 'var(--success)' }} />
                  <h4>All caught up! No clips are currently waiting for manual QC review.</h4>
                </div>
              ) : (
                reviewClips.map(clip => (
                  <div key={clip.id} className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 'bold' }}>Clip ID: {clip.id.substring(0, 8)}...</span>
                        <span className="badge badge-active">{clip.status}</span>
                        <span className="text-muted">{clip.duration_s} seconds</span>
                      </div>
                      
                      {/* Display Intelligence scoring details if present */}
                      {clip.scores && (
                        <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          <span>Hook: {clip.scores.hook_strength || 0}</span>
                          <span>Emotion: {clip.scores.emotional_intensity || 0}</span>
                          <span>Curiosity: {clip.scores.curiosity_gap || 0}</span>
                          <span>Humor: {clip.scores.humor || 0}</span>
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button 
                        onClick={() => handleClipAction(clip.id, true)} 
                        className="btn btn-success"
                        style={{ padding: '8px 16px' }}
                      >
                        <Check size={16} /> Approve & Publish
                      </button>
                      <button 
                        onClick={() => handleClipAction(clip.id, false)} 
                        className="btn"
                        style={{ padding: '8px 16px', backgroundColor: 'var(--danger)' }}
                      >
                        <X size={16} /> Reject
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB 4: ASSET LIBRARY */}
        {activeTab === 'assets' && (
          <div>
            <h1 className="section-title"><Video /> Asset Library</h1>
            <p className="text-muted" style={{ marginBottom: '24px' }}>
              Archive of all successfully generated and published YouTube Shorts.
            </p>

            {publishedClips.length === 0 ? (
              <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                <Video size={48} style={{ marginBottom: '16px' }} />
                <h4>No published clips found in the library.</h4>
              </div>
            ) : (
              <div className="grid-cards">
                {publishedClips.map(clip => (
                  <div key={clip.id} className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <div style={{ height: '140px', backgroundColor: 'rgba(0,0,0,0.4)', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Video size={40} color="var(--accent-primary)" />
                    </div>
                    <h4 style={{ margin: '0 0 8px 0', fontSize: '0.95rem' }}>Clip {clip.id.substring(0, 8)}...</h4>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>Duration: {clip.duration_s}s</div>
                    <span className="badge badge-completed" style={{ alignSelf: 'flex-start' }}>Published</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
