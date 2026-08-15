import React, { useState, useMemo } from 'react';
import type { Channel, CuratedStory } from '../../types';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { BookOpen, FileText, RefreshCw, Sparkles, Mic, Clock } from 'lucide-react';

interface StoriesViewProps {
  channels: Channel[];
  selectedChannelId: string;
  onSelectChannelId: (id: string) => void;
  stories: CuratedStory[];
  onRefreshStories: () => void;
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const StoriesView: React.FC<StoriesViewProps> = ({
  channels,
  selectedChannelId,
  onSelectChannelId,
  stories,
  onRefreshStories,
  showToast
}) => {
  const [submitting, setSubmitting] = useState(false);
  const [voiceProfile, setVoiceProfile] = useState('narrator_neutral_v1');
  const [newStory, setNewStory] = useState({
    title: '',
    body_text: '',
    subreddit: 'r/AskReddit',
    author: ''
  });

  const wordCount = useMemo(() => {
    if (!newStory.body_text.trim()) return 0;
    return newStory.body_text.trim().split(/\s+/).length;
  }, [newStory.body_text]);

  const estimatedDurationSeconds = useMemo(() => {
    return Math.round(wordCount / 2.33); // ~140 words per minute average speaking rate
  }, [wordCount]);

  const formatClassification = useMemo(() => {
    if (wordCount === 0) return 'Empty';
    if (estimatedDurationSeconds <= 60) return '📱 Vertical Short (<60s)';
    if (estimatedDurationSeconds <= 180) return '📱 Extended Short (1-3m)';
    return '🖥️ Long-Form Video (16:9)';
  }, [wordCount, estimatedDurationSeconds]);

  const handleCleanRedditFormatting = () => {
    let text = newStory.body_text;
    text = text.replace(/^#+\s+/gm, '');
    text = text.replace(/EDIT:.*$/gmi, '');
    text = text.replace(/\/u\/[A-Za-z0-9_-]+/g, '');
    text = text.replace(/\/r\/[A-Za-z0-9_-]+/g, '');
    text = text.replace(/\n{3,}/g, '\n\n');
    
    setNewStory(prev => ({ ...prev, body_text: text.trim() }));
    showToast('Cleaned Reddit formatting artifacts from story text', 'info');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStory.title || !newStory.body_text) {
      showToast('Title and story body text are required', 'danger');
      return;
    }

    setSubmitting(true);
    try {
      await api.submitCuratedStory({
        title: newStory.title.trim(),
        body_text: newStory.body_text.trim(),
        subreddit: newStory.subreddit || 'r/AskReddit',
        author: newStory.author || undefined,
        channel_id: selectedChannelId || undefined
      });
      showToast('Story submitted! Autonomous voice & caption pipeline launched.', 'success');
      setNewStory({ title: '', body_text: '', subreddit: 'r/AskReddit', author: '' });
      onRefreshStories();
    } catch (err: any) {
      showToast(err.message || 'Failed to submit story', 'danger');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReQueueAll = async () => {
    try {
      showToast('Re-queuing all stories for voice narration & rendering...', 'info');
      const data = await api.reQueueAllStories();
      showToast(`Successfully re-queued ${data.requeued_stories} stories!`, 'success');
      onRefreshStories();
    } catch (err: any) {
      showToast(err.message || 'Failed to re-queue stories', 'danger');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <BookOpen /> Curated Reddit Story Studio
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Submit narrative text stories for automated Piper neural TTS voiceover, ASS subtitles, and vertical video rendering.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleReQueueAll}>
          <RefreshCw size={16} /> Re-render All Stories
        </button>
      </div>

      <div className="glass-panel" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Automated Story Production Pipeline:</h4>
        <div className="flowchart-container">
          <div className="flowchart-step"><div className="flowchart-node active">1</div><span style={{ fontSize: '0.75rem' }}>Submit Story</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">2</div><span style={{ fontSize: '0.75rem' }}>Script Pacing</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">3</div><span style={{ fontSize: '0.75rem' }}>Piper Neural TTS</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">4</div><span style={{ fontSize: '0.75rem' }}>Whisper Word Timestamps</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">5</div><span style={{ fontSize: '0.75rem' }}>AMF Hardware Compositor</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node completed">6</div><span style={{ fontSize: '0.75rem' }}>Quality Review</span></div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '32px' }}>
        
        {/* Story Ingestion Form */}
        <div className="glass-panel">
          <h3 style={{ marginTop: 0, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} /> Ingest Story Narrative
          </h3>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Target Channel</label>
                <select 
                  value={selectedChannelId} 
                  onChange={e => onSelectChannelId(e.target.value)} 
                  className="input"
                >
                  <option value="">-- Default Story Channel --</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>{c.name} ({c.niche})</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  <Mic size={14} style={{ display: 'inline', marginRight: '4px' }} />
                  Narrator Voice Profile
                </label>
                <select 
                  value={voiceProfile} 
                  onChange={e => setVoiceProfile(e.target.value)} 
                  className="input"
                >
                  <option value="narrator_neutral_v1">🎙️ Lessac High (Neutral Documentary)</option>
                  <option value="motivational_male_v1">🎙️ Ryan High (Energetic Male)</option>
                  <option value="warm_female_v1">🎙️ Amy Medium (Warm Female Storyteller)</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Story Title</label>
              <input 
                className="input" 
                placeholder="Story Title (e.g. AITA for refusing to give up my first class seat?)" 
                value={newStory.title} 
                onChange={e => setNewStory({ ...newStory, title: e.target.value })} 
                required 
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Full Story Narrative Text</label>
                {newStory.body_text && (
                  <button 
                    type="button" 
                    onClick={handleCleanRedditFormatting}
                    style={{ background: 'none', border: 'none', color: '#93c5fd', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <Sparkles size={12} /> Auto-Clean Reddit Artifacts
                  </button>
                )}
              </div>
              <textarea 
                className="input" 
                rows={9}
                placeholder="Paste full Reddit narrative text here... All acronyms (AITA, WIBTA, 21M, $50k) will be automatically expanded for natural human spoken pacing."
                value={newStory.body_text}
                onChange={e => setNewStory({ ...newStory, body_text: e.target.value })}
                required
              />
            </div>

            {/* Live Metrics Row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'rgba(0,0,0,0.25)', borderRadius: '8px', fontSize: '0.82rem' }}>
              <div style={{ display: 'flex', gap: '16px' }}>
                <span>Words: <b>{wordCount}</b></span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={14} /> Est. Duration: <b>{estimatedDurationSeconds}s</b>
                </span>
              </div>
              <span style={{ color: '#93c5fd', fontWeight: 'bold' }}>{formatClassification}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Subreddit</label>
                <input 
                  className="input" 
                  value={newStory.subreddit}
                  onChange={e => setNewStory({ ...newStory, subreddit: e.target.value })}
                  placeholder="r/AskReddit, r/AITA"
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Author / Credit (Optional)</label>
                <input 
                  className="input" 
                  value={newStory.author}
                  onChange={e => setNewStory({ ...newStory, author: e.target.value })}
                  placeholder="u/StoryAuthor"
                />
              </div>
            </div>

            <button type="submit" disabled={submitting} className="btn btn-primary" style={{ marginTop: '8px', padding: '12px' }}>
              {submitting ? 'Synthesizing Audio & Rendering Video...' : '🚀 Submit Story & Start Production'}
            </button>
          </form>
        </div>

        {/* Existing Stories List */}
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Curated Stories Catalog ({stories.length})</h3>
            <button onClick={onRefreshStories} className="btn btn-outline btn-sm">
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {stories.length === 0 ? (
            <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              No stories submitted yet. Submit a story to produce your first narrated video!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '580px', overflowY: 'auto' }}>
              {stories.map(s => (
                <div key={s.id} style={{ padding: '14px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '6px' }}>
                    <div style={{ fontWeight: '600', fontSize: '0.92rem', color: '#f8fafc' }}>{s.title}</div>
                    <Badge status={s.status === 'ready' ? 'succeeded' : s.status} />
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    {s.subreddit || 'r/AskReddit'} {s.author ? `• by ${s.author}` : ''}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)', lineClamp: 2, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {s.body_text}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
