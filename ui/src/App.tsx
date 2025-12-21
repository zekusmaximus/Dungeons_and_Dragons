import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Lobby from './components/Lobby';
import NarrativeDashboard from './components/NarrativeDashboard';
import AccessibilitySettings from './components/AccessibilitySettings';

const queryClient = new QueryClient();

// Global CSS for the app
const globalCSS = `
.app-container {
  min-height: 100vh;
  background-color: #f0e6d2;
  font-family: 'Georgia', serif;
  position: relative;
}

.accessibility-button {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background-color: #8B4513;
  color: white;
  border: none;
  font-size: 24px;
  cursor: pointer;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  transition: all 0.2s;
}

.accessibility-button:hover {
  background-color: #A0522D;
  transform: scale(1.1);
}

.accessibility-button:focus {
  outline: 2px solid #4CAF50;
  outline-offset: 2px;
}
`;

const App: React.FC = () => {
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
    // Settings are automatically applied via CSS classes
  };

  return (
    <QueryClientProvider client={queryClient}>
      <style>{globalCSS}</style>
      <div className="app-container">
        {!selectedSession ? (
          <Lobby
            onSelectSession={setSelectedSession}
            onNewAdventure={handleNewAdventure}
          />
        ) : (
          <NarrativeDashboard
            sessionSlug={selectedSession}
            onBackToLobby={() => setSelectedSession(null)}
          />
        )}

        {/* Accessibility Settings Button - Fixed position */}
        <button
          onClick={() => setShowAccessibilitySettings(true)}
          className="accessibility-button"
          title="Accessibility Settings"
        >
          ♿
        </button>

        {/* Accessibility Settings Modal */}
        {showAccessibilitySettings && (
          <AccessibilitySettings
            onClose={() => setShowAccessibilitySettings(false)}
            onApply={handleApplyAccessibilitySettings}
          />
        )}
      </div>
    </QueryClientProvider>
  );
}

export default App;
