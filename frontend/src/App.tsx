import { useState, useEffect } from 'react';
import { 
  Activity, LayoutDashboard, Settings, RefreshCw, X, Shield, 
  FileText, Film, BookOpen, Play, Pause, FolderCheck, 
  CheckCircle, XCircle 
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

interface ToastItem {
  id: string;
  type: 'success' | 'danger' | 'warning' | 'info';
  text: string;
}

function App() {
  const [activeTab, setActiveTab] = useState('stories');
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [submittingStory, setSubmittingStory] = useState(false);

  const showMessage = (text: string, type: 'success' | 'danger' | 'warning' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, type, text }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };
  
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

  // Telegram Bot Notifications
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);

  const fetchTelegramConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/system/telegram`);
      if (res.ok) {
        const d = await res.json();
        setTelegramConfigured(d.configured);
        if (d.chat_id) setTelegramChatId(d.chat_id);
      }
    } catch (err) {
      console.error('Failed to fetch Telegram config:', err);
    }
  };

  const handleTestTelegram = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!telegramToken || !telegramChatId) {
      showMessage('Bot Token and Chat ID are required', 'danger');
      return;
    }
    setTestingTelegram(true);
    try {
      const res = await fetch(`${API_BASE}/system/telegram/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_token: telegramToken.trim(), chat_id: telegramChatId.trim() })
      });
      if (res.ok) {
        showMessage('Test notification sent to your Telegram chat!', 'success');
        setTelegramConfigured(true);
      } else {
        throw new Error('Failed to send Telegram test message');
      }
    } catch (err: any) {
      showMessage(err.message, 'danger');
    } finally {
      setTestingTelegram(false);
    }
  };

  const [jobs, setJobs] = useState<any[]>([]);
  const [jobStatusFilter, setJobStatusFilter] = useState('all');

  const fetchJobs = async (statusFilter: string = jobStatusFilter) => {
    try {
      const url = statusFilter && statusFilter !== 'all' 
        ? `${API_BASE}/jobs?status=${statusFilter}` 
        : `${API_BASE}/jobs`;
      const res = await fetch(url);
      const data = await res.json();
      setJobs(data.jobs || []);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/retry`, { method: 'POST' });
      if (!res.ok) throw new Error('Retry failed');
      showMessage('Job re-queued successfully!', 'success');
      fetchJobs(jobStatusFilter);
    } catch (err: any) {
      showMessage(err.message, 'danger');
    }
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
      fetchTelegramConfig();
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
    } else if (activeTab === 'jobs') {
      fetchJobs();
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

  const [uploadingFile, setUploadingFile] = useState(false);

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

  const handleUploadLocalBgFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFile(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('license_type', 'owned');
      const res = await fetch(`${API_BASE}/background-assets/upload`, {
        method: 'POST',
        body: formData
      });
      if (!res.ok) throw new Error('Upload failed');
      showMessage(`Video file "${file.name}" uploaded successfully as a background asset!`, 'success');
      fetchBgAssets();
    } catch (err: any) {
      showMessage(err.message, 'danger');
    } finally {
      setUploadingFile(false);
      e.target.value = '';
    }
  };

  return (
    <div className="dashboard-container">
      {/* Floating Toast Notification Stack */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <div className="toast-content">
              {t.type === 'success' && <CheckCircle size={18} className="toast-icon" />}
              {t.type === 'danger' && <XCircle size={18} className="toast-icon" />}
              {t.type === 'info' && <Activity size={18} className="toast-icon" />}
              {t.type === 'warning' && <Shield size={18} className="toast-icon" />}
              <span>{t.text}</span>
            </div>
            <button className="toast-close" onClick={() => removeToast(t.id)}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>

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
            onClick={() => setActiveTab('jobs')} 
            className={`btn ${activeTab === 'jobs' ? 'btn-primary' : 'btn-outline'}`}
            style={{ justifyContent: 'flex-start', padding: '12px 16px' }}
          >
            <Activity size={18} /> Job Queue & Monitor
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

                <form onSubmit={async (e) => {
                  e.preventDefault();
                  if (!newStory.title || !newStory.body_text) { showMessage('Title and story body are required', 'danger'); return; }
                  setSubmittingStory(true);
                  try {
                    const payload: any = {
                      title: newStory.title.trim(),
                      body_text: newStory.body_text.trim(),
                      subreddit: newStory.subreddit || 'r/AskReddit',
                      author: newStory.author || undefined
                    };
                    if (selectedChannelId) {
                      payload.channel_id = selectedChannelId;
                    }
                    const res = await fetch(`${API_BASE}/curated-stories`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(payload)
                    });
                    if (!res.ok) {
                      const errData = await res.json().catch(() => ({}));
                      throw new Error(errData.detail || `Submission failed (${res.status})`);
                    }
                    showMessage('Story submitted successfully! Automated pipeline started.', 'success');
                    setNewStory({ title: '', body_text: '', source_url: '', author: '', subreddit: 'r/AskReddit' });
                    fetchStories();
                  } catch (err: any) { 
                    showMessage(err.message || 'Failed to submit story', 'danger'); 
                  } finally {
                    setSubmittingStory(false);
                  }
                }} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Target Channel</label>
                    <select 
                      value={selectedChannelId} 
                      onChange={e => setSelectedChannelId(e.target.value)} 
                      className="input"
                    >
                      <option value="">-- Default Channel --</option>
                      {channels.map(c => (
                        <option key={c.id} value={c.id}>{c.name} ({c.niche})</option>
                      ))}
                    </select>
                  </div>

                  <input className="input" placeholder="Story Title (e.g. AITA for refusing to give my seat?)" value={newStory.title} onChange={e => setNewStory({...newStory, title: e.target.value})} required />
                  <textarea className="input" placeholder="Full story narrative body text..." rows={6} value={newStory.body_text} onChange={e => setNewStory({...newStory, body_text: e.target.value})} required style={{ resize: 'vertical' }} />
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <input className="input" placeholder="Subreddit (e.g. r/AITA)" value={newStory.subreddit} onChange={e => setNewStory({...newStory, subreddit: e.target.value})} />
                    <input className="input" placeholder="Author (Optional)" value={newStory.author} onChange={e => setNewStory({...newStory, author: e.target.value})} />
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={submittingStory}>
                    {submittingStory ? 'Submitting Story...' : <><Play size={16} /> Submit Story to Pipeline</>}
                  </button>
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

        {/* TAB: JOB QUEUE MONITOR */}
        {activeTab === 'jobs' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div>
                <h1 className="section-title" style={{ margin: 0 }}><Activity /> Job Queue & Execution Monitor</h1>
                <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
                  Real-time visibility into all pipeline background jobs (queued, running, succeeded, failed, dead-letter).
                </p>
              </div>
              <button className="btn btn-outline" onClick={() => fetchJobs(jobStatusFilter)}>
                <RefreshCw size={16} /> Refresh Jobs
              </button>
            </div>

            {/* Job Status Filter Tabs */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', flexWrap: 'wrap' }}>
              {['all', 'queued', 'running', 'succeeded', 'failed', 'dead_letter', 'cancelled'].map(st => (
                <button
                  key={st}
                  onClick={() => { setJobStatusFilter(st); fetchJobs(st); }}
                  className={`btn btn-sm ${jobStatusFilter === st ? 'btn-primary' : 'btn-outline'}`}
                  style={{ textTransform: 'capitalize' }}
                >
                  {st.replace('_', ' ')}
                  <span style={{ marginLeft: '6px', opacity: 0.8, fontSize: '0.75rem' }}>
                    ({st === 'all' ? jobs.length : jobs.filter(j => j.status === st).length})
                  </span>
                </button>
              ))}
            </div>

            {/* Jobs Table */}
            <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
              {jobs.length === 0 ? (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No jobs found for status filter "{jobStatusFilter}".
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.05)', borderBottom: '1px solid var(--border-color)' }}>
                      <th style={{ padding: '14px 18px' }}>Job Type & Trace ID</th>
                      <th style={{ padding: '14px 18px' }}>Status</th>
                      <th style={{ padding: '14px 18px' }}>Attempts</th>
                      <th style={{ padding: '14px 18px' }}>Error Details</th>
                      <th style={{ padding: '14px 18px' }}>Created At</th>
                      <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map(j => (
                      <tr key={j.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ fontWeight: '600', color: '#f8fafc', textTransform: 'capitalize' }}>{j.type.replace('_', ' ')}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'monospace', marginTop: '2px' }}>{j.trace_id}</div>
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <span className={`badge ${
                            j.status === 'succeeded' ? 'badge-completed' :
                            j.status === 'running' ? 'badge-active' :
                            j.status === 'failed' || j.status === 'dead_letter' ? 'badge-pending' : 'badge-active'
                          }`}>
                            {j.status}
                          </span>
                        </td>
                        <td style={{ padding: '14px 18px', fontFamily: 'monospace' }}>
                          {j.attempts} / {j.max_attempts}
                        </td>
                        <td style={{ padding: '14px 18px', maxWidth: '300px' }}>
                          {j.error ? (
                            <span style={{ color: '#fca5a5', fontSize: '0.78rem', wordBreak: 'break-word', fontFamily: 'monospace' }}>
                              {j.error}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>None</span>
                          )}
                        </td>
                        <td style={{ padding: '14px 18px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                          {j.created_at ? new Date(j.created_at.endsWith('Z') ? j.created_at : j.created_at + 'Z').toLocaleString() : '-'}
                        </td>
                        <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                          {(j.status === 'failed' || j.status === 'dead_letter') && (
                            <button onClick={() => handleRetryJob(j.id)} className="btn btn-primary btn-sm">
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
            <h1 className="section-title"><Film /> Background Video Assets Library</h1>
            <p className="text-muted" style={{ marginBottom: '24px' }}>
              Add your own local `.mp4` video files or Creative Commons YouTube URLs to be used as background footage for story videos.
            </p>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
              {/* Option 1: Direct Local Video File Upload */}
              <div className="glass-panel">
                <h3>Option 1: Upload Local Video File (.mp4)</h3>
                <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '14px' }}>
                  Select an `.mp4` file from your computer to upload directly as a background asset.
                </p>
                <label className="btn btn-primary" style={{ display: 'inline-flex', cursor: 'pointer' }}>
                  <FolderCheck size={16} /> {uploadingFile ? 'Uploading Video...' : 'Choose Local MP4 File'}
                  <input type="file" accept="video/mp4" onChange={handleUploadLocalBgFile} disabled={uploadingFile} style={{ display: 'none' }} />
                </label>
              </div>

              {/* Option 2: Register YouTube CC URL */}
              <div className="glass-panel">
                <h3>Option 2: Register YouTube CC Video URL</h3>
                <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '14px' }}>
                  Enter a YouTube video URL to automatically download Creative Commons background footage.
                </p>
                <form onSubmit={handleAddBgAsset} style={{ display: 'flex', gap: '8px' }}>
                  <input className="input" placeholder="YouTube URL (https://www.youtube.com/watch?v=...)" value={newBgUrl} onChange={e => setNewBgUrl(e.target.value)} required />
                  <button type="submit" className="btn btn-primary btn-sm">Register URL</button>
                </form>
              </div>
            </div>

            <h3 style={{ marginBottom: '16px' }}>Registered Background Assets Pool ({bgAssets.length})</h3>
            <div className="grid-cards">
              {bgAssets.length === 0 ? (
                <div className="glass-panel" style={{ gridColumn: '1 / -1', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No background assets registered yet. Upload an `.mp4` file or register a YouTube URL above!
                </div>
              ) : (
                bgAssets.map(bg => (
                  <div key={bg.id} className="glass-panel">
                    <h4 style={{ wordBreak: 'break-all', fontSize: '0.85rem', marginBottom: '10px' }}>{bg.source_url}</h4>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="badge badge-active">{bg.status}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Key: {bg.storage_key?.substring(0, 16)}...</span>
                    </div>
                  </div>
                ))
              )}
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

            {/* Telegram Bot Real-Time Alerts */}
            <div className="glass-panel" style={{ marginTop: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Shield size={18} /> Telegram Bot Real-Time Event Alerts
                </h4>
                <span className={`badge ${telegramConfigured ? 'badge-completed' : 'badge-pending'}`}>
                  {telegramConfigured ? 'Bot Connected & Active' : 'Not Configured'}
                </span>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Receive instant Telegram push notifications on your phone for video downloads, Whisper transcriptions, viral moment scoring, Reddit story narration, video renders, and job failures.
              </p>
              <form onSubmit={handleTestTelegram} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '12px' }}>
                <input
                  type="password"
                  className="input"
                  placeholder="Telegram Bot Token (from @BotFather)"
                  value={telegramToken}
                  onChange={e => setTelegramToken(e.target.value)}
                  required
                />
                <input
                  type="text"
                  className="input"
                  placeholder="Chat ID (e.g. 123456789 or @your_channel)"
                  value={telegramChatId}
                  onChange={e => setTelegramChatId(e.target.value)}
                  required
                />
                <button type="submit" className="btn btn-primary" disabled={testingTelegram}>
                  {testingTelegram ? 'Testing...' : 'Test & Save Telegram Alert'}
                </button>
              </form>
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
