import React, { useState, useEffect } from 'react';
import type { ContentSource } from '../../types';
import { api } from '../../services/api';
import { Shield } from 'lucide-react';

interface RightsViewProps {
  sources: ContentSource[];
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const RightsView: React.FC<RightsViewProps> = ({ sources, showToast }) => {
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [rightsStatus, setRightsStatus] = useState('unknown');
  const [evidenceRef, setEvidenceRef] = useState('');

  useEffect(() => {
    if (sources.length > 0 && !selectedSourceId) {
      setSelectedSourceId(sources[0].id);
    }
  }, [sources, selectedSourceId]);

  useEffect(() => {
    if (selectedSourceId) {
      api.getRightsStatus(selectedSourceId)
        .then(data => {
          setRightsStatus(data.status || 'unknown');
          setEvidenceRef(data.evidence_ref || '');
        })
        .catch(err => console.error('Rights fetch error:', err));
    }
  }, [selectedSourceId]);

  const handleSaveRights = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSourceId) return;
    try {
      await api.saveRightsStatus(selectedSourceId, rightsStatus, evidenceRef.trim());
      showToast('Rights & compliance audit record saved!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to save rights status', 'danger');
    }
  };

  return (
    <div>
      <h1 className="section-title"><Shield /> Rights & Copyright Compliance Audit</h1>
      <p className="text-muted" style={{ marginBottom: '24px' }}>
        Record audit evidence and legal rights permission status for content acquisition sources.
      </p>

      <div className="glass-panel" style={{ maxWidth: '600px' }}>
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
              <option value="owned">owned (100% Original Content)</option>
              <option value="licensed">licensed (Creative Commons / License Purchased)</option>
              <option value="permission_granted">permission_granted (Written Creator Consent)</option>
              <option value="unknown">unknown (Requires Review)</option>
              <option value="denied">denied (Forbidden Source)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Evidence Reference / Documentation Note</label>
            <input 
              className="input" 
              placeholder="Evidence Reference (URL, License PDF link, or document note)" 
              value={evidenceRef} 
              onChange={e => setEvidenceRef(e.target.value)} 
            />
          </div>

          <button type="submit" className="btn btn-primary">Save Compliance Audit Record</button>
        </form>
      </div>
    </div>
  );
};
