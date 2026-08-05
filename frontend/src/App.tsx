import { useState, useEffect } from 'react';
import { 
  Activity, LayoutDashboard, Settings, RefreshCw, X, Shield, 
  FileText, Film, BookOpen, Play, Pause, FolderCheck, 
  Sparkles, CheckCircle, XCircle 
} from 'lucide-react';
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
  source_post_id?: string;
  storage_key?: string;
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
  const [activeTab, setActiveTab] = useState('stories');
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'danger' | 'info' } | null>(null);
  
  // Channels
  const [channels, setChannels] = useState<Channel[]>([]);
  const [newChannel, setNewChannel] = useState({
    name: '',
    slug: '',
    niche: 'Reddit Stories',
    project_id: 'default_project',
    youtube_api_key: '',
    language: 'en'
  });
  
  // Content Sources
  const [selectedChannelId, setSelectedChannelId] = useState('');
  const [sources, setSources] = useState<ContentSource[]>([]);
  const [newSource, setNewSource] = useState({
    external_ref: 'UC_x5XG1OV2P6uZZ5FSM9Ttw',
    type: 'youtube_channel',
    poll_interval_minutes: 60,
    max_new_videos_per_poll: 1
  });

  // Rights & Compliance
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [rightsStatus, setRightsStatus] = useState('unknown');
  const [evidenceRef, setEvidenceRef] = useState('');

  // Pipeline/Health/Quotas
  const [health, setHealth] = useState<any>(null);
  const [models, setModels] = useState<Record<string, ModelHealth>>({});
  const [quotas, setQuotas] = useState<Quota[]>([]);
  const [healthLoading, setHealthLoading] = useState(false);

  // Review Clips & Assets
  const [reviewClips, setReviewClips] = useState<Clip[]>([]);
  const [publishedClips, setPublishedClips] = useState<Clip[]>([]);

  // Curated Stories
  const [stories, setStories] = useState<any[]>([]);
  const [storySourceId, setStorySourceId] = useState('');
  const [newStory, setNewStory] = useState({ 
    title: '', 
    body_text: '', 
    source_url: '', 
    author: '', 
    subreddit: 'r/AskReddit' 
  });

  // Background Assets
  const [bgAssets, setBgAssets] = useState<any[]>([]);
  const [newBgUrl, setNewBgUrl] = useState('');

  const showMessage = (text: string, type: 'success' | 'danger' | 'info' = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const fetchChannels = async () => {
    try {
      const res = await fetch(`${API_BASE}/channels/`);
      const data = await res.json();
      const list = data.channels || [];
      setChannels(list);
      if (list.length > 0 && !selectedChannelId) {
        setSelectedChannelId(list[0].id);
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
      const srcList: ContentSource[] = data.sources || [];
      setSources(srcList);
      if (srcList.length > 0) {
        setSelectedSourceId(srcList[0].id);
        const storySrc = srcList.find(s => s.type === 'curated_story');
        if (storySrc) {
          setStorySourceId(storySrc.id);
        } else {
          setStorySourceId(srcList[0].id);
        }
      } else {
        setSelectedSourceId('');
        setStorySourceId('');
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

  const fetchStories = async () => {
    try {
      const res = await fetch(`${API_BASE}/curated-stories`);
      if (res.ok) {
        const d = await res.json();
        setStories(d || []);
      }
    } catch (err) {
      console.error('Failed to fetch stories:', err);
    }
  };

  const fetchBgAssets = async () => {
    try {
      const res = await fetch(`${API_BASE}/background-assets`);
      if (res.ok) {
        const d = await res.json();
        setBgAssets(d || []);
      }
    } catch (err) {
      console.error('Failed to fetch background assets:', err);
    }
  };

  useEffect(() => {
    fetchChannels();
  }, []);

  useEffect(() => {
    if (activeTab === 'overview') {
      fetchSystemData();
    } else if (activeTab === 'candidates' || activeTab === 'assets') {
      fetchClips();
    } else if (activeTab === 'stories') {
      fetchStories();
      if (selectedChannelId) fetchSources(selectedChannelId);
    } else if (activeTab === 'bgassets') {
      fetchBgAssets();
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
    }
  }, [selectedSourceId]);

  const handleAddChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChannel.name || !newChannel.slug) {
      showMessage('Channel Name and Slug are required', 'danger');
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
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to create channel');
      const created = await res.json();
      showMessage(`Channel "${created.name}" created!`, 'success');
      setNewChannel({ name: '', slug: '', niche: 'Reddit Stories', project_id: 'default_project', youtube_api_key: '', language: 'en' });
      fetchChannels();
      setSelectedChannelId(created.id);
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleAddSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChannelId) {
      showMessage('Please select a channel first', 'danger');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/sources/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel_id: selectedChannelId,
          type: newSource.type,
          external_ref: newSource.external_ref,
          config: {
            poll_interval_minutes: Number(newSource.poll_interval_minutes),
            max_new_videos_per_poll: Number(newSource.max_new_videos_per_poll)
          }
        })
      });
      if (!res.ok) throw new Error('Failed to add source');
      showMessage('Content Source added successfully!', 'success');
      fetchSources(selectedChannelId);
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleAutoCreateStorySource = async () => {
    if (!selectedChannelId) {
      showMessage('Select or create a channel first', 'danger');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/sources/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel_id: selectedChannelId,
          type: 'curated_story',
          external_ref: 'reddit_curated_stories',
          config: { poll_interval_minutes: 60, max_new_videos_per_poll: 1 }
        })
      });
      if (!res.ok) throw new Error('Failed to auto-create story source');
      const created = await res.json();
      showMessage('Curated Story Source created and selected!', 'success');
      fetchSources(selectedChannelId);
      setStorySourceId(created.id);
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleToggleSourceActive = async (sourceId: string, currentActive: boolean) => {
    try {
      const res = await fetch(`${API_BASE}/sources/${sourceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: !currentActive })
      });
      if (res.ok) {
        showMessage(`Source ${!currentActive ? 'activated' : 'paused'}`, 'success');
        fetchSources(selectedChannelId);
      }
    } catch (err: any) {
      showMessage('Failed to update source status', 'danger');
    }
  };

  const handleClipAction = async (clipId: string, approve: boolean) => {
    try {
      const targetStatus = approve ? 'ready' : 'rejected';
      const res = await fetch(`${API_BASE}/clips/${clipId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: targetStatus })
      });
      if (!res.ok) throw new Error('Failed to update clip status');
      showMessage(`Clip ${approve ? 'approved for export' : 'rejected'}!`, approve ? 'success' : 'info');
      fetchClips();
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleSaveRights = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSourceId) return;
    try {
      const res = await fetch(`${API_BASE}/rights/${selectedSourceId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: rightsStatus,
          evidence_ref: evidenceRef,
          reviewed_by: 'Operator'
        })
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to update rights');
      showMessage('Rights compliance status saved!', 'success');
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  const handleAddBgAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBgUrl) return;
    try {
      const res = await fetch(`${API_BASE}/background-assets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: newBgUrl, license_type: 'licensed' })
      });
      if (!res.ok) throw new Error('Failed to register background asset');
      showMessage('Background asset YouTube URL registered!', 'success');
      setNewBgUrl('');
      fetchBgAssets();
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
          <div className="status-indicator" />
          <span style={{ fontWeight: 'bold', fontSize: '1.2rem', letterSpacing: '-0.03em', color: '#f8fafc' }}>
            YTAuto <span style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', padding: '2px 6px', background: 'rgba(59,130,246,0.2)', borderRadius: '4px' }}>v1.5</span>
          </span>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '6px', flexGrow: 1 }}>
          <button 
            onClick={() => setActiveTab('stories')} 
            className={`btn ${activeTab === 'stories' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <BookOpen size={18} /> Curated Stories
          </button>

          <button 
            onClick={() => setActiveTab('setup')} 
            className={`btn ${activeTab === 'setup' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <Settings size={18} /> Setup & Sources
          </button>

          <button 
            onClick={() => setActiveTab('overview')} 
            className={`btn ${activeTab === 'overview' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <LayoutDashboard size={18} /> System Overview
          </button>

          <button 
            onClick={() => setActiveTab('candidates')} 
            className={`btn ${activeTab === 'candidates' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <Activity size={18} /> Quality Gate Review
            {reviewClips.length > 0 && <span className="badge badge-pending">{reviewClips.length}</span>}
          </button>

          <button 
            onClick={() => setActiveTab('assets')} 
            className={`btn ${activeTab === 'assets' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <FolderCheck size={18} /> Exported Assets
          </button>

          <button 
            onClick={() => setActiveTab('bgassets')} 
            className={`btn ${activeTab === 'bgassets' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <Film size={18} /> Background Footage
          </button>

          <button 
            onClick={() => setActiveTab('rights')} 
            className={`btn ${activeTab === 'rights' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <Shield size={18} /> Rights & Compliance
          </button>
        </nav>

        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
          <div>Local Exports Directory:</div>
          <code style={{ fontSize: '0.7rem', color: '#93c5fd', wordBreak: 'break-all' }}>C:\dev\YTAuto\exports</code>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {message && (
          <div className="glass-panel" style={{ marginBottom: '24px', borderLeft: `4px solid ${message.type === 'success' ? 'var(--success)' : message.type === 'danger' ? 'var(--danger)' : 'var(--accent-primary)'}`, padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>{message.text}</span>
            <button onClick={() => setMessage(null)} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}><X size={16} /></button>
          </div>
        )}

        {/* TAB: CURATED STORIES */}
        {activeTab === 'stories' && (
          <div>
            <h1 className="section-title"><BookOpen /> Curated Reddit Stories Production</h1>
            <p className="text-muted" style={{ marginBottom: '24px' }}>
              Submit Reddit stories or narratives for automated voice synthesis, subtitle rendering, and local export.
            </p>

            {/* Visual Flowchart Stepper */}
            <div className="glass-panel" style={{ marginBottom: '24px' }}>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Automated Story Pipeline Flowchart:</h4>
              <div className="flowchart-container">
                <div className="flowchart-step"><div className="flowchart-node active">1</div><span style={{ fontSize: '0.75rem' }}>Operator Submit</span></div>
                <div className="flowchart-arrow">→</div>
                <div className="flowchart-step"><div className="flowchart-node active">2</div><span style={{ fontSize: '0.75rem' }}>LLM Script Format</span></div>
                <div className="flowchart-arrow">→</div>
                <div className="flowchart-step"><div className="flowchart-node active">3</div><span style={{ fontSize: '0.75rem' }}>Piper TTS Audio</span></div>
                <div className="flowchart-arrow">→</div>
                <div className="flowchart-step"><div className="flowchart-node active">4</div><span style={{ fontSize: '0.75rem' }}>Whisper ASS Subtitles</span></div>
                <div className="flowchart-arrow">→</div>
                <div className="flowchart-step"><div className="flowchart-node active">5</div><span style={{ fontSize: '0.75rem' }}>FFmpeg CC Crop Render</span></div>
                <div className="flowchart-arrow">→</div>
                <div className="flowchart-step"><div className="flowchart-node completed">6</div><span style={{ fontSize: '0.75rem' }}>Local Export & .txt</span></div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
              {/* Submit Form */}
              <div className="glass-panel">
                <h3 style={{ marginTop: 0, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={18} /> Submit Story for Processing
                </h3>
                
                {sources.filter(s => s.type === 'curated_story').length === 0 ? (
                  <div style={{ padding: '16px', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '8px', marginBottom: '16px' }}>
                    <p style={{ margin: '0 0 12px 0', fontSize: '0.85rem', color: '#fcd34d' }}>
                      No Curated Story source found for the selected channel.
                    </p>
                    <button onClick={handleAutoCreateStorySource} className="btn btn-primary btn-sm">
                      <Sparkles size={14} /> Auto-Create Story Content Source
                    </button>
                  </div>
                ) : null}

                <form onSubmit={async (e) => {
                  e.preventDefault();
                  if (!storySourceId) { showMessage('Select a curated_story content source first', 'danger'); return; }
                  if (!newStory.title || !newStory.body_text) { showMessage('Title and story body are required', 'danger'); return; }
                  try {
                    const res = await fetch(`${API_BASE}/curated-stories`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ content_source_id: storySourceId, ...newStory })
                    });
                    if (!res.ok) throw new Error((await res.json()).detail || 'Submission failed');
                    showMessage('Story submitted! Automated pipeline started.', 'success');
                    setNewStory({ title: '', body_text: '', source_url: '', author: '', subreddit: 'r/AskReddit' });
                    fetchStories();
                  } catch (err: any) { showMessage(err.message, 'danger'); }
                }} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Target Content Source</label>
                    <select 
                      value={storySourceId} 
                      onChange={e => setStorySourceId(e.target.value)} 
                      className="input"
                    >
                      <option value="">Select Curated Story Source...</option>
                      {sources.filter(s => s.type === 'curated_story').map(s => (
                        <option key={s.id} value={s.id}>{s.external_ref} (Channel ID: {s.channel_id.substring(0,8)})</option>
                      ))}
                    </select>
                  </div>

                  <input className="input" placeholder="Story Title (e.g. AITA for refusing to give my seat?)" value={newStory.title} onChange={e => setNewStory({...newStory, title: e.target.value})} required />
                  <textarea className="input" placeholder="Full story narrative body text..." rows={6} value={newStory.body_text} onChange={e => setNewStory({...newStory, body_text: e.target.value})} required style={{ resize: 'vertical' }} />
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <input className="input" placeholder="Subreddit (e.g. r/AITA)" value={newStory.subreddit} onChange={e => setNewStory({...newStory, subreddit: e.target.value})} />
                    <input className="input" placeholder="Author (Optional)" value={newStory.author} onChange={e => setNewStory({...newStory, author: e.target.value})} />
                  </div>
                  <button type="submit" className="btn btn-primary"><Play size={16} /> Submit Story to Pipeline</button>
                </form>
              </div>

              {/* Recent Submissions List */}
              <div className="glass-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{ margin: 0 }}>Active Pipeline Stories</h3>
                  <button className="btn btn-outline btn-sm" onClick={fetchStories}><RefreshCw size={14} /></button>
                </div>
                {stories.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No stories submitted yet.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '480px', overflowY: 'auto' }}>
                    {stories.map((s: any) => (
                      <div key={s.id} style={{ padding: '14px', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '0.9rem' }}>{s.title}</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className={`badge ${s.status === 'done' ? 'badge-completed' : s.status === 'failed' ? 'badge-pending' : 'badge-active'}`}>{s.status}</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{s.subreddit || 'r/AskReddit'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB: SETUP */}
        {activeTab === 'setup' && (
          <div>
            <h1 className="section-title"><Settings /> Setup Channels & Content Sources</h1>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
              {/* Section A: Channel Management */}
              <div className="glass-panel">
                <h3>Channel Profiles</h3>
                <form onSubmit={handleAddChannel} style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                  <input className="input" placeholder="Channel Name" value={newChannel.name} onChange={e => setNewChannel({...newChannel, name: e.target.value})} required />
                  <input className="input" placeholder="Slug (e.g. reddit_narrations)" value={newChannel.slug} onChange={e => setNewChannel({...newChannel, slug: e.target.value})} required />
                  <input className="input" placeholder="Niche (e.g. Reddit Stories)" value={newChannel.niche} onChange={e => setNewChannel({...newChannel, niche: e.target.value})} />
                  <button type="submit" className="btn btn-primary">Add Channel Profile</button>
                </form>
              </div>

              {/* Section B: Content Sources */}
              <div className="glass-panel">
                <h3>Configured Content Sources</h3>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Select Active Channel:</label>
                  <select value={selectedChannelId} onChange={e => setSelectedChannelId(e.target.value)} className="input">
                    <option value="">-- Select Channel --</option>
                    {channels.map(c => (
                      <option key={c.id} value={c.id}>{c.name} ({c.slug})</option>
                    ))}
                  </select>
                </div>

                <form onSubmit={handleAddSource} style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px', padding: '14px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                  <h4 style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Add New Source</h4>
                  <select className="input" value={newSource.type} onChange={e => setNewSource({...newSource, type: e.target.value})}>
                    <option value="youtube_channel">YouTube Channel</option>
                    <option value="curated_story">Curated Reddit Story</option>
                  </select>
                  <input className="input" placeholder="External Ref (Channel ID / Name)" value={newSource.external_ref} onChange={e => setNewSource({...newSource, external_ref: e.target.value})} required />
                  <button type="submit" className="btn btn-primary btn-sm">Add Content Source</button>
                </form>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {sources.map(s => (
                    <div key={s.id} style={{ padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 'bold' }}>{s.external_ref}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Type: {s.type} | Max per poll: {s.config?.max_new_videos_per_poll || 1}</div>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => handleToggleSourceActive(s.id, s.active)} className={`btn btn-sm ${s.active ? 'btn-outline' : 'btn-primary'}`}>
                          {s.active ? <Pause size={12} /> : <Play size={12} />} {s.active ? 'Pause' : 'Activate'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB: QUALITY GATE REVIEW */}
        {activeTab === 'candidates' && (
          <div>
            <h1 className="section-title"><Activity /> Quality Gate Review Queue</h1>
            {reviewClips.length === 0 ? (
              <div className="glass-panel" style={{ textAlign: 'center', padding: '40px' }}>
                <h3>No clips waiting in the review queue.</h3>
              </div>
            ) : (
              <div className="grid-cards">
                {reviewClips.map(clip => (
                  <div key={clip.id} className="glass-panel">
                    <h4>Clip ID: {clip.id.substring(0, 8)}...</h4>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Duration: {clip.duration_s}s</p>
                    <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
                      <button onClick={() => handleClipAction(clip.id, true)} className="btn btn-success btn-sm"><CheckCircle size={14} /> Approve</button>
                      <button onClick={() => handleClipAction(clip.id, false)} className="btn btn-outline btn-sm" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}><XCircle size={14} /> Reject</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB: EXPORTED ASSETS */}
        {activeTab === 'assets' && (
          <div>
            <h1 className="section-title"><FolderCheck /> Local Exported Assets Library</h1>
            <p className="text-muted" style={{ marginBottom: '24px' }}>
              Directory location: <code style={{ color: '#93c5fd' }}>C:\dev\YTAuto\exports\</code>
            </p>

            <div className="grid-cards">
              {publishedClips.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                  <h4>No published clips found in the library yet.</h4>
                </div>
              ) : (
                publishedClips.map(clip => (
                  <div key={clip.id} className="glass-panel" style={{ display: 'flex', flexDirection: 'column', padding: '16px' }}>
                    <div style={{ height: '240px', borderRadius: '8px', overflow: 'hidden', backgroundColor: 'black', marginBottom: '16px' }}>
                      <video 
                        src={`${API_BASE}/clips/${clip.id}/video`} 
                        controls 
                        preload="metadata"
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    </div>
                    <h4 style={{ margin: '0 0 8px 0', fontSize: '0.95rem' }}>Clip ID: {clip.id.substring(0, 8)}...</h4>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>Duration: {clip.duration_s}s</div>
                    <span className="badge badge-completed" style={{ alignSelf: 'flex-start' }}>Exported</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB: BACKGROUND ASSETS */}
        {activeTab === 'bgassets' && (
          <div>
            <h1 className="section-title"><Film /> Creative Commons Background Assets</h1>
            
            <div className="glass-panel" style={{ marginBottom: '24px' }}>
              <h3>Add YouTube Background Footage</h3>
              <form onSubmit={handleAddBgAsset} style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <input className="input" placeholder="YouTube Video URL (e.g. https://www.youtube.com/watch?v=...)" value={newBgUrl} onChange={e => setNewBgUrl(e.target.value)} required />
                <button type="submit" className="btn btn-primary">Register CC URL</button>
              </form>
            </div>

            <div className="grid-cards">
              {bgAssets.map(bg => (
                <div key={bg.id} className="glass-panel">
                  <h4 style={{ wordBreak: 'break-all', fontSize: '0.85rem' }}>{bg.source_url}</h4>
                  <span className="badge badge-active">{bg.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB: RIGHTS & COMPLIANCE */}
        {activeTab === 'rights' && (
          <div>
            <h1 className="section-title"><Shield /> Rights & Compliance Audit</h1>
            <div className="glass-panel">
              <form onSubmit={handleSaveRights} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Content Source</label>
                  <select value={selectedSourceId} onChange={e => setSelectedSourceId(e.target.value)} className="input">
                    {sources.map(s => (
                      <option key={s.id} value={s.id}>{s.external_ref} ({s.type})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Rights Status</label>
                  <select value={rightsStatus} onChange={e => setRightsStatus(e.target.value)} className="input">
                    <option value="owned">owned</option>
                    <option value="licensed">licensed</option>
                    <option value="permission_granted">permission_granted</option>
                    <option value="unknown">unknown</option>
                    <option value="denied">denied</option>
                  </select>
                </div>
                <input className="input" placeholder="Evidence Reference (URL or document note)" value={evidenceRef} onChange={e => setEvidenceRef(e.target.value)} />
                <button type="submit" className="btn btn-primary">Save Compliance Audit Record</button>
              </form>
            </div>
          </div>
        )}

        {/* TAB: SYSTEM OVERVIEW */}
        {activeTab === 'overview' && (
          <div>
            <h1 className="section-title"><LayoutDashboard /> System Health & Status</h1>
            <button onClick={fetchSystemData} className="btn btn-outline btn-sm" style={{ marginBottom: '16px' }}><RefreshCw size={14} className={healthLoading ? 'spin' : ''} /> Refresh Status</button>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              <div className="glass-panel">
                <h4>System Infrastructure</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>PostgreSQL Database:</span>
                    <span className={`badge ${health?.db === 'ok' ? 'badge-completed' : 'badge-pending'}`}>{health?.db || 'ok'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Redis Queue:</span>
                    <span className={`badge ${health?.redis === 'ok' ? 'badge-completed' : 'badge-pending'}`}>{health?.redis || 'ok'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>MinIO Object Storage:</span>
                    <span className={`badge ${health?.minio === 'ok' ? 'badge-completed' : 'badge-pending'}`}>{health?.minio || 'ok'}</span>
                  </div>
                </div>
              </div>

              <div className="glass-panel">
                <h4>Model Runtime Status</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '16px' }}>
                  {Object.entries(models).map(([stage, status]) => (
                    <div key={stage} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Stage: {stage}</span>
                      <span className={`badge ${status.healthy ? 'badge-completed' : 'badge-pending'}`}>{status.model_name} ({status.healthy ? 'Healthy' : 'Offline'})</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {quotas.length > 0 && (
              <div className="glass-panel" style={{ marginTop: '24px' }}>
                <h4>YouTube Quota Pools</h4>
                {quotas.map(q => (
                  <div key={q.project_id} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
                    Project ID: {q.project_id} | Remaining Units: {q.remaining}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
