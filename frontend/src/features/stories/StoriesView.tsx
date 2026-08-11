import React, { useState, useMemo } from 'react';
import type { Channel, CuratedStory } from '../../types';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { BookOpen, FileText, Play, RefreshCw, Sparkles } from 'lucide-react';

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
    return Math.round(wordCount / 2.33);
  }, [wordCount]);

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ margin: 0 }}>
            <BookOpen /> Curated Reddit Story Studio
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Submit narrative text stories for automated voice synthesis, ASS subtitles, and video rendering.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleReQueueAll}>
          <RefreshCw size={16} /> Re-render All Stories
        </button>
      </div>

      <div className="glass-panel" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Automated Story Pipeline Flowchart:</h4>
        <div className="flowchart-container">
          <div className="flowchart-step"><div className="flowchart-node active">1</div><span style={{ fontSize: '0.75rem' }}>Operator Submit</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">2</div><span style={{ fontSize: '0.75rem' }}>Script Clean</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">3</div><span style={{ fontSize: '0.75rem' }}>Piper TTS</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">4</div><span style={{ fontSize: '0.75rem' }}>Whisper Subtitles</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node active">5</div><span style={{ fontSize: '0.75rem' }}>FFmpeg Crop</span></div>
          <div className="flowchart-arrow">→</div>
          <div className="flowchart-step"><div className="flowchart-node completed">6</div><span style={{ fontSize: '0.75rem' }}>Quality Review</span></div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
        
        <div className="glass-panel">
          <h3 style={{ marginTop: 0, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} /> Ingest Story Narrative
          </h3>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Target YouTube Channel</label>
              <select 
                value={selectedChannelId} 
                onChange={e => onSelectChannelId(e.target.value)} 
                className="input"
              >
                <option value="">-- Default Reddit Shorts Channel --</option>
                {channels.map(c => (
                  <option key={c.id} value={c.id}>{c.name} ({c.niche})</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Story Title</label>
              <input 
                className="input" 
                placeholder="Story Title (e.g. AITA for refusing to give up my seat?)" 
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
                    className="btn btn-outline btn-sm"
                    style={{ fontSize: '0.75rem', padding: '2px 8px' }}
                  >
                    <Sparkles size={12} /> Clean Reddit Formatting
                  </button>
                )}
              </div>
              <textarea 
                className="input" 
                placeholder="Paste story body narrative text here..." 
                rows={7} 
                value={newStory.body_text} 
                onChange={e => setNewStory({ ...newStory, body_text: e.target.value })} 
                required 
                style={{ resize: 'vertical' }} 
              />
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                <span>Word Count: <strong>{wordCount} words</strong></span>
                <span style={{ color: estimatedDurationSeconds <= 60 ? '#6ee7b7' : '#fcd34d' }}>
                  Estimated Narration: <strong>~{estimatedDurationSeconds}s</strong> {estimatedDurationSeconds <= 60 ? '(Shorts Suitable)' : '(Long-Form)'}
                </span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <input className="input" placeholder="Subreddit (e.g. r/AITA)" value={newStory.subreddit} onChange={e => setNewStory({ ...newStory, subreddit: e.target.value })} />
              <input className="input" placeholder="Author (Optional)" value={newStory.author} onChange={e => setNewStory({ ...newStory, author: e.target.value })} />
            </div>

            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Submitting Story...' : <><Play size={16} /> Submit Story to Production Pipeline</>}
            </button>

          </form>
        </div>

        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ margin: 0 }}>Active Ingested Stories</h3>
            <button className="btn btn-outline btn-sm" onClick={onRefreshStories}>
              <RefreshCw size={14} />
            </button>
          </div>

          {stories.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', textAlign: 'center', padding: '32px' }}>
              No stories submitted yet. Submit a story using the form!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '500px', overflowY: 'auto' }}>
              {stories.map(s => (
                <div key={s.id} style={{ padding: '14px', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '0.9rem' }}>{s.title}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Badge status={s.status} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{s.subreddit || 'r/AskReddit'}</span>
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
