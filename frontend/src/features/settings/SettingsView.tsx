import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { Badge } from '../../components/ui/Badge';
import { Settings, Bell, CheckCircle, Moon, Activity, Sliders } from 'lucide-react';

interface SettingsViewProps {
  showToast: (text: string, type?: 'success' | 'danger' | 'warning' | 'info') => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ showToast }) => {
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [allowedChatIds, setAllowedChatIds] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [botTokenMasked, setBotTokenMasked] = useState<string | null>(null);
  const [testingTelegram, setTestingTelegram] = useState(false);

  // Notification Preferences
  const [categories, setCategories] = useState<Record<string, boolean>>({
    SYSTEM: true,
    JOBS: true,
    CONTENT: true,
    QUOTA: true,
    SECURITY: true
  });
  const [minSeverities, setMinSeverities] = useState<Record<string, string>>({
    SYSTEM: 'WARNING',
    JOBS: 'INFO',
    CONTENT: 'INFO',
    QUOTA: 'WARNING',
    SECURITY: 'INFO'
  });

  // Quiet Hours & Thresholds
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(false);
  const [quietHoursStart, setQuietHoursStart] = useState('23:00');
  const [quietHoursEnd, setQuietHoursEnd] = useState('07:00');
  const [timezone, setTimezone] = useState('Africa/Nairobi');
  const [dedupeWindow, setDedupeWindow] = useState(300);
  const [quotaWarning, setQuotaWarning] = useState(70);
  const [quotaCritical, setQuotaCritical] = useState(90);

  // Delivery Audit Logs
  const [deliveryLogs, setDeliveryLogs] = useState<any[]>([]);

  const fetchTelegramSettings = async () => {
    try {
      const data = await api.getTelegramConfig();
      setConnectionStatus(data.connection_status || (data.configured ? 'healthy' : 'disconnected'));
      if (data.bot_token_masked) setBotTokenMasked(data.bot_token_masked);
      if (data.chat_id) setTelegramChatId(data.chat_id);
      if (data.allowed_chat_ids) setAllowedChatIds(data.allowed_chat_ids.join(', '));
      if (data.preferences) {
        setCategories(data.preferences.enabled_categories || categories);
        setMinSeverities(data.preferences.min_severity || minSeverities);
      }
      if (data.quiet_hours) {
        setQuietHoursEnabled(data.quiet_hours.enabled || false);
        setQuietHoursStart(data.quiet_hours.start || '23:00');
        setQuietHoursEnd(data.quiet_hours.end || '07:00');
        setTimezone(data.quiet_hours.timezone || 'Africa/Nairobi');
      }
      if (data.thresholds) {
        setDedupeWindow(data.thresholds.dedupe_window_seconds || 300);
        setQuotaWarning(data.thresholds.quota_warning_threshold || 70);
        setQuotaCritical(data.thresholds.quota_critical_threshold || 90);
      }
    } catch (err) {
      console.error('Telegram config fetch error:', err);
    }
  };

  const fetchDeliveryLogs = async () => {
    try {
      const data = await api.getTelegramLogs(15);
      setDeliveryLogs(data.logs || []);
    } catch (err) {
      console.error('Delivery logs fetch error:', err);
    }
  };

  useEffect(() => {
    fetchTelegramSettings();
    fetchDeliveryLogs();
  }, []);

  const handleTestAndSaveConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!telegramToken && !botTokenMasked) {
      showToast('Telegram Bot Token is required', 'danger');
      return;
    }
    if (!telegramChatId) {
      showToast('Telegram Chat ID is required', 'danger');
      return;
    }

    setTestingTelegram(true);
    try {
      const parsedAllowed = allowedChatIds.split(',').map(s => s.trim()).filter(Boolean);
      await api.saveTelegramConfig(telegramToken || botTokenMasked || '', telegramChatId.trim(), parsedAllowed);
      
      const testRes = await api.testTelegram(telegramToken || botTokenMasked || '', telegramChatId.trim());
      showToast(`✓ Empirical Telegram test passed: ${testRes.message || 'Delivered'}`, 'success');
      fetchTelegramSettings();
      fetchDeliveryLogs();
    } catch (err: any) {
      showToast(err.message || 'Telegram test failed', 'danger');
    } finally {
      setTestingTelegram(false);
    }
  };

  const handleSavePreferences = async () => {
    try {
      await api.saveTelegramPreferences({
        enabled_categories: categories,
        min_severity: minSeverities,
        quiet_hours_enabled: quietHoursEnabled,
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
        timezone,
        dedupe_window_seconds: Number(dedupeWindow),
        quota_warning_threshold: Number(quotaWarning),
        quota_critical_threshold: Number(quotaCritical)
      });
      showToast('Notification policies, quiet hours & thresholds saved!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to save preferences', 'danger');
    }
  };

  return (
    <div>
      <h1 className="section-title"><Settings /> System Configuration & Remote Telegram Operations</h1>

      {/* 1. Connection Card */}
      <div className="glass-panel" style={{ maxWidth: '850px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bell size={18} /> Telegram Operations & Push Alert Subsystem
          </h3>
          <Badge status={connectionStatus} />
        </div>

        <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
          YTAuto operates autonomously and uses Telegram to notify you of critical milestones, job failures, quality review items, and YouTube API quota limits.
        </p>

        <form onSubmit={handleTestAndSaveConnection} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Telegram Bot Token (from @BotFather)</label>
              <input 
                type="password" 
                className="input" 
                placeholder={botTokenMasked ? `Saved (${botTokenMasked})` : "e.g. 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"} 
                value={telegramToken} 
                onChange={e => setTelegramToken(e.target.value)} 
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Primary Chat / Channel ID</label>
              <input 
                type="text" 
                className="input" 
                placeholder="e.g. 123456789 or -100123456789" 
                value={telegramChatId} 
                onChange={e => setTelegramChatId(e.target.value)} 
                required 
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Authorized Chat IDs for Bot Commands (/status, /jobs, /review)</label>
            <input 
              type="text" 
              className="input" 
              placeholder="Comma-separated chat IDs allowed to issue commands e.g. 123456789, 987654321" 
              value={allowedChatIds} 
              onChange={e => setAllowedChatIds(e.target.value)} 
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px', display: 'block' }}>
              Only messages from authorized Chat IDs will execute bot commands. Unauthorized command attempts are logged.
            </span>
          </div>

          <button type="submit" className="btn btn-primary" disabled={testingTelegram} style={{ alignSelf: 'flex-start' }}>
            {testingTelegram ? 'Testing & Verifying Connection...' : <><CheckCircle size={16} /> Save Credentials & Test Telegram API Connection</>}
          </button>

        </form>
      </div>

      {/* 2. Notification Policy & Quiet Hours */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', maxWidth: '850px', marginBottom: '24px' }}>
        
        {/* Category Toggles */}
        <div className="glass-panel">
          <h4 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={16} /> Granular Category Notification Policies
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {['SYSTEM', 'JOBS', 'CONTENT', 'QUOTA', 'SECURITY'].map(cat => (
              <div key={cat} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.88rem' }}>
                  <input 
                    type="checkbox" 
                    checked={categories[cat] ?? true} 
                    onChange={e => setCategories({ ...categories, [cat]: e.target.checked })} 
                  />
                  <strong>{cat} Alerts</strong>
                </label>

                <select 
                  value={minSeverities[cat] || 'INFO'} 
                  onChange={e => setMinSeverities({ ...minSeverities, [cat]: e.target.value })}
                  className="input" 
                  style={{ width: '110px', padding: '4px 8px', fontSize: '0.78rem' }}
                >
                  <option value="INFO">INFO+</option>
                  <option value="SUCCESS">SUCCESS+</option>
                  <option value="WARNING">WARNING+</option>
                  <option value="ERROR">ERROR+</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>
            ))}
          </div>

          <button onClick={handleSavePreferences} className="btn btn-outline btn-sm" style={{ marginTop: '16px', width: '100%' }}>
            Save Category Policies
          </button>
        </div>

        {/* Quiet Hours & Thresholds */}
        <div className="glass-panel">
          <h4 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Moon size={16} /> Quiet Hours & Alert Thresholds
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '0.85rem' }}>
            
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={quietHoursEnabled} 
                onChange={e => setQuietHoursEnabled(e.target.checked)} 
              />
              <span>Enable Quiet Hours (CRITICAL alerts always bypass)</span>
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label className="text-muted" style={{ display: 'block', marginBottom: '4px' }}>Quiet Start Time</label>
                <input type="text" className="input" value={quietHoursStart} onChange={e => setQuietHoursStart(e.target.value)} placeholder="23:00" />
              </div>
              <div>
                <label className="text-muted" style={{ display: 'block', marginBottom: '4px' }}>Quiet End Time</label>
                <input type="text" className="input" value={quietHoursEnd} onChange={e => setQuietHoursEnd(e.target.value)} placeholder="07:00" />
              </div>
            </div>

            <div>
              <label className="text-muted" style={{ display: 'block', marginBottom: '4px' }}>System Timezone</label>
              <select className="input" value={timezone} onChange={e => setTimezone(e.target.value)}>
                <option value="Africa/Nairobi">Africa/Nairobi (EAT, UTC+3)</option>
                <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
                <option value="UTC">Coordinated Universal Time (UTC)</option>
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label className="text-muted" style={{ display: 'block', marginBottom: '4px' }}>Quota Warning (%)</label>
                <input type="number" className="input" value={quotaWarning} onChange={e => setQuotaWarning(Number(e.target.value))} />
              </div>
              <div>
                <label className="text-muted" style={{ display: 'block', marginBottom: '4px' }}>Dedupe Window (s)</label>
                <input type="number" className="input" value={dedupeWindow} onChange={e => setDedupeWindow(Number(e.target.value))} />
              </div>
            </div>

            <button onClick={handleSavePreferences} className="btn btn-primary btn-sm" style={{ marginTop: '6px' }}>
              Save Quiet Hours & Thresholds
            </button>
          </div>
        </div>

      </div>

      {/* 3. Delivery Audit Log */}
      <div className="glass-panel" style={{ maxWidth: '850px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={16} /> Recent Telegram Delivery Audit Logs
          </h4>
          <button className="btn btn-outline btn-sm" onClick={fetchDeliveryLogs}>Refresh Audit Log</button>
        </div>

        {deliveryLogs.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
            No Telegram delivery records logged yet.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.05)', borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '10px 12px' }}>Timestamp</th>
                <th style={{ padding: '10px 12px' }}>Event Type</th>
                <th style={{ padding: '10px 12px' }}>Severity</th>
                <th style={{ padding: '10px 12px' }}>Status</th>
                <th style={{ padding: '10px 12px' }}>Details / Error</th>
              </tr>
            </thead>
            <tbody>
              {deliveryLogs.map(log => (
                <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                    {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>{log.event_type}</td>
                  <td style={{ padding: '10px 12px' }}><Badge status={log.severity.toLowerCase()} /></td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      color: log.status === 'sent' ? '#6ee7b7' : log.status.startsWith('suppressed') ? '#fcd34d' : '#fca5a5',
                      fontWeight: 'bold'
                    }}>
                      {log.status.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                    {log.error || (log.status === 'sent' ? `Message ID: ${log.telegram_message_id || 'OK'}` : 'Suppressed')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Storage Maintenance & Footprint Optimization */}
      <div className="glass-panel" style={{ maxWidth: '850px', marginTop: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Settings size={16} /> Storage Lifecycle & Footprint Optimization
            </h4>
            <p className="text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.8rem' }}>
              Purge full-length downloaded source videos from MinIO once rendering is completed to reclaim disk storage.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button 
              className="btn btn-outline btn-sm"
              style={{ borderColor: 'rgba(245,158,11,0.4)', color: '#fcd34d' }}
              onClick={async () => {
                try {
                  showToast('Purging assets older than 7 days (preserving background videos)...', 'info');
                  const res = await api.purgeAgedAssets(7);
                  showToast(`Purged ${res.deleted_objects} aged files (freed ${res.freed_gb} GB)! All Reddit background videos preserved.`, 'success');
                } catch (err: any) {
                  showToast(err.message || 'Purge failed', 'danger');
                }
              }}
            >
              🗓️ Purge 7-Day Old Assets
            </button>
            <button 
              className="btn btn-outline btn-sm"
              onClick={async () => {
                try {
                  showToast('Flushing completed raw source videos...', 'info');
                  const res = await api.flushRawStorage();
                  showToast(`Reclaimed ${res.freed_mb} MB (${res.deleted_objects} raw objects purged)!`, 'success');
                } catch (err: any) {
                  showToast(err.message || 'Flush failed', 'danger');
                }
              }}
            >
              🧹 Flush Used Raw Sources
            </button>
            <button 
              className="btn btn-outline btn-sm"
              onClick={async () => {
                try {
                  showToast('Re-exporting all published clips to local C:\\dev\\YTAuto\\exports...', 'info');
                  const res = await api.reExportClips();
                  showToast(`Exported ${res.re_exported_clips} clips to local folder!`, 'success');
                } catch (err: any) {
                  showToast(err.message || 'Export failed', 'danger');
                }
              }}
            >
              📦 Sync Local Exports
            </button>
          </div>
        </div>
      </div>

    </div>
  );
};

