import { useState, useEffect, useCallback } from 'react';
import type { RouteKey, Channel, ContentSource, CuratedStory, BackgroundAsset } from './types';
import { api } from './services/api';
import { useToast } from './hooks/useToast';
import { useRealtimeData } from './hooks/useRealtimeData';

import { Sidebar } from './components/layout/Sidebar';
import { ToastStack } from './components/ui/ToastStack';

import { OverviewView } from './features/overview/OverviewView';
import { StoriesView } from './features/stories/StoriesView';
import { JobsView } from './features/jobs/JobsView';
import { QualityGateView } from './features/review/QualityGateView';
import { AssetsView } from './features/assets/AssetsView';
import { BackgroundsView } from './features/backgrounds/BackgroundsView';
import { SourcesView } from './features/sources/SourcesView';
import { RightsView } from './features/rights/RightsView';
import { SettingsView } from './features/settings/SettingsView';

import './index.css';

export function App() {
  const [currentRoute, setCurrentRoute] = useState<RouteKey>('overview');
  const { toasts, showToast, removeToast } = useToast();

  const {
    jobs,
    reviewClips,
    publishedClips,
    health,
    models,
    quotas,
    loading: realtimeLoading,
    pendingReviewCount,
    failedJobsCount,
    refreshAll
  } = useRealtimeData();

  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState('');
  const [sources, setSources] = useState<ContentSource[]>([]);

  const [stories, setStories] = useState<CuratedStory[]>([]);
  const [bgAssets, setBgAssets] = useState<BackgroundAsset[]>([]);

  const parseRouteFromHash = useCallback((): RouteKey => {
    const hash = window.location.hash.replace('#/', '').replace('#', '');
    const validRoutes: RouteKey[] = ['overview', 'stories', 'jobs', 'review', 'assets', 'backgrounds', 'sources', 'rights', 'settings'];
    if (validRoutes.includes(hash as RouteKey)) {
      return hash as RouteKey;
    }
    return 'overview';
  }, []);

  useEffect(() => {
    setCurrentRoute(parseRouteFromHash());

    const handleHashChange = () => {
      setCurrentRoute(parseRouteFromHash());
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [parseRouteFromHash]);

  const handleNavigate = (route: RouteKey) => {
    window.location.hash = `#/${route}`;
    setCurrentRoute(route);
  };

  const fetchChannels = async () => {
    try {
      const list = await api.getChannels();
      setChannels(list);
      if (list.length > 0 && !selectedChannelId) {
        setSelectedChannelId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch channels:', err);
    }
  };

  const fetchSources = async (channelId: string) => {
    if (!channelId) return;
    try {
      const list = await api.getSources(channelId);
      setSources(list);
    } catch (err) {
      console.error('Failed to fetch sources:', err);
    }
  };

  const fetchStories = async () => {
    try {
      const list = await api.getCuratedStories();
      setStories(list || []);
    } catch (err) {
      console.error('Failed to fetch stories:', err);
    }
  };

  const fetchBgAssets = async () => {
    try {
      const list = await api.getBackgroundAssets();
      setBgAssets(list || []);
    } catch (err) {
      console.error('Failed to fetch background assets:', err);
    }
  };

  useEffect(() => {
    fetchChannels();
    fetchStories();
    fetchBgAssets();
  }, []);

  useEffect(() => {
    if (selectedChannelId) {
      fetchSources(selectedChannelId);
    }
  }, [selectedChannelId]);

  const handleRetryJob = async (jobId: string) => {
    try {
      await api.retryJob(jobId);
      showToast('Job re-queued successfully!', 'success');
      refreshAll();
    } catch (err: any) {
      showToast(err.message || 'Retry failed', 'danger');
    }
  };

  return (
    <div className="dashboard-container">
      <ToastStack toasts={toasts} onRemove={removeToast} onNavigate={handleNavigate} />

      <Sidebar
        currentRoute={currentRoute}
        onNavigate={handleNavigate}
        pendingReviewCount={pendingReviewCount}
        failedJobsCount={failedJobsCount}
        onRefreshAll={refreshAll}
        isRefreshing={realtimeLoading}
      />

      <main className="main-content">
        {currentRoute === 'overview' && (
          <OverviewView
            health={health}
            models={models}
            quotas={quotas}
            jobs={jobs}
            reviewClips={reviewClips}
            publishedClips={publishedClips}
            onNavigate={handleNavigate}
            onRefresh={refreshAll}
            onRetryJob={handleRetryJob}
          />
        )}

        {currentRoute === 'stories' && (
          <StoriesView
            channels={channels}
            selectedChannelId={selectedChannelId}
            onSelectChannelId={setSelectedChannelId}
            stories={stories}
            onRefreshStories={fetchStories}
            showToast={showToast}
          />
        )}

        {currentRoute === 'jobs' && (
          <JobsView
            jobs={jobs}
            onRefreshJobs={refreshAll}
            showToast={showToast}
          />
        )}

        {currentRoute === 'review' && (
          <QualityGateView
            reviewClips={reviewClips}
            onRefreshClips={refreshAll}
            showToast={showToast}
          />
        )}

        {currentRoute === 'assets' && (
          <AssetsView
            publishedClips={publishedClips}
            onRefreshClips={refreshAll}
            showToast={showToast}
          />
        )}

        {currentRoute === 'backgrounds' && (
          <BackgroundsView
            bgAssets={bgAssets}
            onRefreshBgAssets={fetchBgAssets}
            showToast={showToast}
          />
        )}

        {currentRoute === 'sources' && (
          <SourcesView
            channels={channels}
            selectedChannelId={selectedChannelId}
            onSelectChannelId={setSelectedChannelId}
            sources={sources}
            onRefreshChannels={fetchChannels}
            onRefreshSources={fetchSources}
            showToast={showToast}
          />
        )}

        {currentRoute === 'rights' && (
          <RightsView
            sources={sources}
            showToast={showToast}
          />
        )}

        {currentRoute === 'settings' && (
          <SettingsView
            showToast={showToast}
          />
        )}
      </main>
    </div>
  );
}

export default App;
