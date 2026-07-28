import { useState } from 'react';
import { Activity, Video, LayoutDashboard } from 'lucide-react';
import './index.css';

// Mock Data for Demo
const MOCK_WORKFLOWS = [
  { id: '1', title: 'Lex Fridman #402', status: 'completed' },
  { id: '2', title: 'Huberman Lab #89', status: 'active' },
  { id: '3', title: 'My First Million', status: 'pending' },
];

const MOCK_CANDIDATES = [
  { id: 'c1', text: 'The reason startups fail is distribution...', score: 28, status: 'pending_review' },
  { id: 'c2', text: 'I saw a bird today...', score: 12, status: 'rejected' },
];

const MOCK_ASSETS = [
  { id: 'a1', title: 'Lex Fridman Viral Clip', status: 'published', url: '#' },
];

function App() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
          <div className="status-indicator"></div>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Autonomous Media</h2>
        </div>
        
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
        {activeTab === 'overview' && (
          <div>
            <h1 className="section-title"><LayoutDashboard /> Pipeline Overview</h1>
            <div className="grid-cards">
              {MOCK_WORKFLOWS.map(wf => (
                <div key={wf.id} className="glass-panel">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <h3 style={{ margin: '0 0 16px 0' }}>{wf.title}</h3>
                    <span className={`badge badge-${wf.status}`}>{wf.status}</span>
                  </div>
                  <p className="text-muted" style={{ fontSize: '0.875rem' }}>
                    Tracking end-to-end extraction and publishing pipeline.
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'candidates' && (
          <div>
            <h1 className="section-title"><Activity /> Candidate Review</h1>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {MOCK_CANDIDATES.map(cand => (
                <div key={cand.id} className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h4 style={{ margin: '0 0 8px 0', color: 'var(--accent-primary)' }}>Score: {cand.score}/30</h4>
                    <p style={{ margin: 0, fontStyle: 'italic' }}>"{cand.text}"</p>
                  </div>
                  <div>
                    {cand.status === 'pending_review' ? (
                      <button className="btn btn-success">Approve & Render</button>
                    ) : (
                      <span className="badge badge-completed">Rejected</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'assets' && (
          <div>
            <h1 className="section-title"><Video /> Asset Library</h1>
            <div className="grid-cards">
              {MOCK_ASSETS.map(asset => (
                <div key={asset.id} className="glass-panel" style={{ textAlign: 'center' }}>
                  <div style={{ height: '200px', backgroundColor: 'rgba(0,0,0,0.5)', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Video size={48} color="var(--text-secondary)" />
                  </div>
                  <h4 style={{ margin: '0 0 8px 0' }}>{asset.title}</h4>
                  <span className="badge badge-completed">Published to YouTube</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
