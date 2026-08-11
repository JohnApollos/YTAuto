import React from 'react';
import type { ToastItem, RouteKey } from '../../types';
import { CheckCircle, XCircle, Activity, Shield, X, ArrowRight } from 'lucide-react';

interface ToastStackProps {
  toasts: ToastItem[];
  onRemove: (id: string) => void;
  onNavigate?: (route: RouteKey) => void;
}

export const ToastStack: React.FC<ToastStackProps> = ({ toasts, onRemove, onNavigate }) => {
  return (
    <div className="toast-container" role="status" aria-live="polite">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <div className="toast-content">
            {t.type === 'success' && <CheckCircle size={18} className="toast-icon" />}
            {t.type === 'danger' && <XCircle size={18} className="toast-icon" />}
            {t.type === 'info' && <Activity size={18} className="toast-icon" />}
            {t.type === 'warning' && <Shield size={18} className="toast-icon" />}
            <div>
              {t.title && <div style={{ fontWeight: 'bold', marginBottom: '2px' }}>{t.title}</div>}
              <span>{t.text}</span>
              {t.actionRoute && onNavigate && (
                <button 
                  onClick={() => { onNavigate(t.actionRoute as RouteKey); onRemove(t.id); }}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginLeft: '10px', color: '#93c5fd', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline', fontWeight: 'bold' }}
                >
                  View <ArrowRight size={12} />
                </button>
              )}
            </div>
          </div>
          <button className="toast-close" onClick={() => onRemove(t.id)} aria-label="Close notification">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
};
