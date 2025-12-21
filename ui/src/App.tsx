import React, { useEffect, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import PlayerStart from './pages/PlayerStart';
import CharacterWizard from './pages/CharacterWizard';
import PlayerTable from './pages/PlayerTable';
import Lobby from './components/Lobby';
import NarrativeDashboard from './components/NarrativeDashboard';
import AccessibilitySettings from './components/AccessibilitySettings';

type RouteState =
  | { name: 'start' }
  | { name: 'wizard'; slug: string }
  | { name: 'table'; slug: string }
  | { name: 'advanced' };

const queryClient = new QueryClient();

const parseLocation = (): RouteState => {
  const parts = window.location.pathname.split('/').filter(Boolean);
  if (parts[0] === 'advanced') return { name: 'advanced' };
  if (parts[0] === 'character' && parts[1]) return { name: 'wizard', slug: parts[1] };
  if (parts[0] === 'play' && parts[1]) return { name: 'table', slug: parts[1] };
  return { name: 'start' };
};

const pathForRoute = (route: RouteState) => {
  if (route.name === 'advanced') return '/advanced';
  if (route.name === 'wizard') return `/character/${route.slug}`;
  if (route.name === 'table') return `/play/${route.slug}`;
  return '/';
};

const AdvancedView: React.FC<{ onExit: () => void }> = ({ onExit }) => {
  const queryClient = useQueryClient();
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [showAccessibilitySettings, setShowAccessibilitySettings] = useState(false);

  const handleNewAdventure = async (hookId: string) => {
    try {
      const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hook_id: hookId }),
      });
      if (!response.ok) {
        throw new Error('Failed to create a new adventure');
      }
      const data = await response.json();
      setSelectedSession(data.slug);
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    } catch (err) {
      console.error('Unable to start new adventure', err);
    }
  };

  const handleApplyAccessibilitySettings = (settings: any) => {
    console.log("Accessibility settings applied:", settings);
  };

  return (
    <div className="advanced-container">
      <div className="advanced-bar">
        <button className="ghost" onClick={onExit}>Back to Player Mode</button>
        <span className="subtle">Advanced dashboard</span>
      </div>
      {!selectedSession ? (
        <Lobby onSelectSession={setSelectedSession} onNewAdventure={handleNewAdventure} />
      ) : (
        <NarrativeDashboard sessionSlug={selectedSession} onBackToLobby={() => setSelectedSession(null)} />
      )}

      <button
        onClick={() => setShowAccessibilitySettings(true)}
        className="accessibility-button"
        title="Accessibility Settings"
      >
        Aa
      </button>
      {showAccessibilitySettings && (
        <AccessibilitySettings
          onClose={() => setShowAccessibilitySettings(false)}
          onApply={handleApplyAccessibilitySettings}
        />
      )}
    </div>
  );
};

// Global CSS for the app
const globalCSS = `
:root {
  font-family: 'Georgia', serif;
}
body {
  margin: 0;
  background: #f7f1e3;
}
.app-shell {
  min-height: 100vh;
}
.accessibility-button {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background-color: #8B4513;
  color: white;
  border: none;
  font-size: 18px;
  cursor: pointer;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  transition: all 0.2s;
}
.accessibility-button:hover {
  background-color: #A0522D;
  transform: scale(1.05);
}
.accessibility-button:focus {
  outline: 2px solid #4CAF50;
  outline-offset: 2px;
}
.ghost {
  background: transparent;
  border: 1px solid #b9864c;
  color: #8c5a2b;
  border-radius: 10px;
  padding: 8px 12px;
  cursor: pointer;
}
.subtle { color: #6d5138; }
.advanced-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}
`;

const App: React.FC = () => {
  const [route, setRoute] = useState<RouteState>(() => parseLocation());

  const navigate = (next: RouteState) => {
    setRoute(next);
    const target = pathForRoute(next);
    if (window.location.pathname !== target) {
      window.history.pushState({}, '', target);
    }
  };

  useEffect(() => {
    const handler = () => setRoute(parseLocation());
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  const renderRoute = useMemo(() => {
    if (route.name === 'advanced') {
      return <AdvancedView onExit={() => navigate({ name: 'start' })} />;
    }
    if (route.name === 'wizard') {
      return (
        <CharacterWizard
          sessionSlug={route.slug}
          onComplete={(slug) => navigate({ name: 'table', slug })}
          onBack={() => navigate({ name: 'start' })}
        />
      );
    }
    if (route.name === 'table') {
      return (
        <PlayerTable
          sessionSlug={route.slug}
          onBack={() => navigate({ name: 'start' })}
          onAdvanced={() => navigate({ name: 'advanced' })}
        />
      );
    }
    return (
      <PlayerStart
        onBeginWizard={(slug) => navigate({ name: 'wizard', slug })}
        onContinue={(slug) => navigate({ name: 'table', slug })}
        onAdvanced={() => navigate({ name: 'advanced' })}
      />
    );
  }, [route]);

  return (
    <QueryClientProvider client={queryClient}>
      <style>{globalCSS}</style>
      <div className="app-shell">
        {renderRoute}
      </div>
    </QueryClientProvider>
  );
};

export default App;
