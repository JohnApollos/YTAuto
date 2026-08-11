import React from 'react';
import type { RouteKey } from '../../types';
import { LayoutDashboard, BookOpen, Activity, CheckCircle, FolderCheck, Film, Settings, Shield, RefreshCw } from 'lucide-react';

interface SidebarProps {
  currentRoute: RouteKey;
  onNavigate: (route: RouteKey) => void;
  pendingReviewCount: number;
  failedJobsCount: number;
  onRefreshAll?: () => void;
  isRefreshing?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentRoute,
  onNavigate,
  pendingReviewCount,
  failedJobsCount,
  onRefreshAll,
  isRefreshing
}) => {
  const getBtnClass = (route: RouteKey) => 
    `btn ${currentRoute === route ? 'btn-primary' : 'btn-outline'}`;

  return (
    <aside className="sidebar">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="status-indicator" title="System Operational" />
          <span style={{ fontWeight: 'bold', fontSize: '1.25rem', letterSpacing: '-0.03em', color: '#f8fafc' }}>
            YTAuto <span style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', padding: '2px 6px', background: 'rgba(59,130,246,0.2)', borderRadius: '4px' }}>v1.5</span>
          </span>
        </div>
        {onRefreshAll && (
          <button 
            className="toast-close" 
            onClick={onRefreshAll} 
            title="Refresh System Data"
            aria-label="Refresh System Data"
          >
            <RefreshCw size={14} className={isRefreshing ? 'spin' : ''} />
          </button>
        )}
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '20px', flexGrow: 1, overflowY: 'auto', paddingRight: '4px' }}>
        
        <div>
          <div className="nav-group-title">COMMAND CENTER</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <button onClick={() => onNavigate('overview')} className={getBtnClass('overview')} style={{ justifyContent: 'flex-start' }}>
              <LayoutDashboard size={18} /> Overview
            </button>
          </div>
        </div>

        <div>
          <div className="nav-group-title">PRODUCTION WORKFLOWS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <button onClick={() => onNavigate('stories')} className={getBtnClass('stories')} style={{ justifyContent: 'flex-start' }}>
              <BookOpen size={18} /> Reddit Story Studio
            </button>
            <button onClick={() => onNavigate('jobs')} className={getBtnClass('jobs')} style={{ justifyContent: 'flex-start', position: 'relative' }}>
              <Activity size={18} /> Job Queue & Monitor
              {failedJobsCount > 0 && (
                <span className="badge badge-pending" style={{ marginLeft: 'auto', fontSize: '0.7rem' }}>
                  {failedJobsCount} Failed
                </span>
              )}
            </button>
            <button onClick={() => onNavigate('review')} className={getBtnClass('review')} style={{ justifyContent: 'flex-start', position: 'relative' }}>
              <CheckCircle size={18} /> Quality Gate Review
              {pendingReviewCount > 0 && (
                <span className="badge badge-completed" style={{ marginLeft: 'auto', fontSize: '0.7rem' }}>
                  {pendingReviewCount} Ready
                </span>
              )}
            </button>
            <button onClick={() => onNavigate('assets')} className={getBtnClass('assets')} style={{ justifyContent: 'flex-start' }}>
              <FolderCheck size={18} /> Exported Video Assets
            </button>
          </div>
        </div>

        <div>
          <div className="nav-group-title">MEDIA ASSETS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <button onClick={() => onNavigate('backgrounds')} className={getBtnClass('backgrounds')} style={{ justifyContent: 'flex-start' }}>
              <Film size={18} /> Background Video Pool
            </button>
          </div>
        </div>

        <div>
          <div className="nav-group-title">SYSTEM CONFIGURATION</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <button onClick={() => onNavigate('sources')} className={getBtnClass('sources')} style={{ justifyContent: 'flex-start' }}>
              <Settings size={18} /> Channels & Sources
            </button>
            <button onClick={() => onNavigate('rights')} className={getBtnClass('rights')} style={{ justifyContent: 'flex-start' }}>
              <Shield size={18} /> Rights & Compliance
            </button>
            <button onClick={() => onNavigate('settings')} className={getBtnClass('settings')} style={{ justifyContent: 'flex-start' }}>
              <Settings size={18} /> Alerts & Settings
            </button>
          </div>
        </div>

      </nav>

      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
        <div>Local Exports Directory:</div>
        <code style={{ fontSize: '0.7rem', color: '#93c5fd', wordBreak: 'break-all' }}>C:\dev\YTAuto\exports</code>
      </div>
    </aside>
  );
};
