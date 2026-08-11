import React from 'react';
import { CheckCircle, AlertTriangle, XCircle, Clock, Play } from 'lucide-react';

interface BadgeProps {
  status: string;
  count?: number;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ status, count, className = '' }) => {
  const normalized = status.toLowerCase();

  let variant = 'badge-active';
  let icon = <Clock size={12} />;
  let label = status.replace('_', ' ');

  if (normalized === 'succeeded' || normalized === 'done' || normalized === 'published' || normalized === 'qc_passed' || normalized === 'ok' || normalized === 'healthy' || normalized === 'ready') {
    variant = 'badge-completed';
    icon = <CheckCircle size={12} />;
  } else if (normalized === 'failed' || normalized === 'dead_letter' || normalized === 'error' || normalized === 'offline' || normalized === 'rejected') {
    variant = 'badge-pending'; // red tinted
    icon = <XCircle size={12} />;
  } else if (normalized === 'queued' || normalized === 'warning' || normalized === 'unknown') {
    variant = 'badge-pending';
    icon = <AlertTriangle size={12} />;
  } else if (normalized === 'running') {
    variant = 'badge-active';
    icon = <Play size={12} className="spin" />;
  }

  return (
    <span className={`badge ${variant} ${className}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
      {icon}
      <span>{label}</span>
      {count !== undefined && <span style={{ marginLeft: '4px', opacity: 0.9 }}>({count})</span>}
    </span>
  );
};
