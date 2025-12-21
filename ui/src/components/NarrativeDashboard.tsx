import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import AdventureJournal from './AdventureJournal';
import TurnConsole from './TurnConsole';
import LLMConfig from './LLMConfig';
import CharacterSheet from './CharacterSheet';
import ExplorationMap from './ExplorationMap';
import TurnStakesPanel from './TurnStakesPanel';
import DialogueSystem from './DialogueSystem';

interface NarrativeDashboardProps {
  sessionSlug: string;
  onBackToLobby: () => void;
}

const NarrativeDashboard: React.FC<NarrativeDashboardProps> = ({ sessionSlug, onBackToLobby }) => {
  const [activeTab, setActiveTab] = useState<'journal' | 'adventure' | 'character' | 'settings' | 'map'>('adventure');
  const [showLLMConfig, setShowLLMConfig] = useState(false);
  const [showCharacterSheet, setShowCharacterSheet] = useState(false);

  const { data: sessionState, isLoading: isStateLoading } = useQuery({
    queryKey: ['state', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/state`).then(r => r.json()),
  });

  const { data: character, isLoading: isCharacterLoading } = useQuery({
    queryKey: ['character', sessionSlug],
    queryFn: () => fetch(`/api/data/characters/${sessionSlug}.json`).then(r => r.json()),
  });

  const { data: currentTurn, isLoading: isTurnLoading } = useQuery({
    queryKey: ['turn', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/turn`).then(r => r.json()),
  });

  const isLoading = isStateLoading || isCharacterLoading || isTurnLoading;
  const [showDialogue, setShowDialogue] = useState(false);
  const [currentNPC, setCurrentNPC] = useState<string | null>(null);

  // Get current scene description from turn data
  const currentScene = currentTurn?.prompt || "Your adventure begins...";

  const handleQuickAction = async (action: string) => {
    // Mock quick action handler - in a real implementation, this would call the API
    const actionMessages = {
      'search': "You carefully search the area and find some interesting items!",
      'talk': "You look around for someone to talk to...",
      'fight': "You prepare for combat, ready to face any challenges!",
      'rest': "You take a short rest, recovering some of your strength."
    };

    const message = actionMessages[action as keyof typeof actionMessages] || "You perform an action.";

    // For talk action, we could open a dialogue with a random NPC
    if (action === 'talk') {
      const mockNPCs = ['guard-001', 'merchant-001', 'villager-001'];
      const randomNPC = mockNPCs[Math.floor(Math.random() * mockNPCs.length)];
      setCurrentNPC(randomNPC);
      setShowDialogue(true);
    }

    // In a real implementation, you would:
    // 1. Call the appropriate API endpoint
    // 2. Update the game state
    // 3. Refresh the turn data
    
    console.log(`Quick action: ${action}`, message);
  };

  // Extract character name and basic info
  const characterName = character?.name || "Adventurer";
  const characterClass = character?.class || "Unknown";
  const characterLevel = character?.level || 1;
  const characterHP = sessionState?.hp || "Unknown";
  const characterLocation = sessionState?.location || "Unknown lands";

  return (
    <div className="narrative-dashboard">
      {/* Add CSS to the head */}
      <style>{dashboardCSS}</style>

      {/* Header with character info */}
      <div className="dashboard-header">
        <div className="character-info">
          <div className="character-portrait">
            <div className="portrait-placeholder">
              {characterClass.charAt(0).toUpperCase()}
            </div>
          </div>
          <div className="character-details">
            <h2>{characterName}</h2>
            <p className="character-subtitle">
              Level {characterLevel} {characterClass} • {characterHP} HP
            </p>
            <p className="location-info">
              📍 {characterLocation}
            </p>
          </div>
        </div>

        <div className="dashboard-controls">
          <button onClick={onBackToLobby} className="back-button">
            ← Back to Lobby
          </button>
          <button
            onClick={() => setShowCharacterSheet(true)}
            className="character-sheet-button"
          >
            👤 Character
          </button>
          <button
            onClick={() => setActiveTab('map')}
            className="map-button"
          >
            🗺️ Map
          </button>
          <button
            onClick={() => setShowLLMConfig(!showLLMConfig)}
            className="settings-button"
          >
            ⚙️ Settings
          </button>
        </div>
      </div>

      {/* Dialogue System Modal */}
      {showDialogue && currentNPC && (
        <DialogueSystem
          sessionSlug={sessionSlug}
          npcId={currentNPC}
          onClose={() => setShowDialogue(false)}
          onDialogueEnd={() => {
            setShowDialogue(false);
            // In a real implementation, you would update relationships here
            console.log('Dialogue ended with', currentNPC);
          }}
        />
      )}

      {/* Character Sheet Modal */}
      {showCharacterSheet && (
        <CharacterSheet
          sessionSlug={sessionSlug}
          onClose={() => setShowCharacterSheet(false)}
        />
      )}

      {/* LLM Config Modal */}
      {showLLMConfig && (
        <div className="modal-overlay">
          <div className="modal-content">
            <LLMConfig onConfigSaved={() => setShowLLMConfig(false)} />
            <button
              onClick={() => setShowLLMConfig(false)}
              className="modal-close"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="dashboard-main">
        {activeTab === 'map' ? (
          <div className="full-width-section">
            <ExplorationMap
              sessionSlug={sessionSlug}
              onLocationClick={(location) => {
                // Handle location click - could set scene or show details
                console.log('Location clicked:', location);
              }}
            />
          </div>
        ) : (
          <>
            {/* Current Scene Panel */}
            <div className="current-scene-panel">
              <h3>🌄 Current Scene</h3>
              {isLoading ? (
                <div className="loading-scene">
                  <div className="loading-spinner"></div>
                  <p>Loading your adventure...</p>
                </div>
              ) : (
                <div className="scene-content">
                  <TurnStakesPanel
                    sessionSlug={sessionSlug}
                    sessionState={sessionState}
                    currentTurn={currentTurn}
                    character={character}
                  />
                  <p className="scene-description">{currentScene}</p>

                  {/* Quick Action Buttons */}
                  <div className="quick-actions">
                    <button
                      onClick={() => setActiveTab('map')}
                      className="action-button primary"
                      title="Open exploration map"
                    >
                      🗺️ Explore
                    </button>
                    <button
                      onClick={() => handleQuickAction('search')}
                      className="action-button"
                      title="Search the current area"
                    >
                      🔍 Search
                    </button>
                    <button
                      onClick={() => handleQuickAction('talk')}
                      className="action-button"
                      title="Initiate conversation"
                    >
                      💬 Talk
                    </button>
                    <button
                      onClick={() => handleQuickAction('fight')}
                      className="action-button"
                      title="Prepare for combat"
                    >
                      ⚔️ Fight
                    </button>
                    <button
                      onClick={() => handleQuickAction('rest')}
                      className="action-button"
                      title="Take a rest"
                    >
                      🛌️ Rest
                    </button>
                  </div>

                  {/* Turn Console */}
                  <div className="turn-console-section">
                    <TurnConsole sessionSlug={sessionSlug} />
                  </div>
                </div>
              )}
            </div>

            {/* Adventure Journal */}
            <div className="adventure-journal-section">
              <AdventureJournal sessionSlug={sessionSlug} />
            </div>
          </>
        )}
      </div>

      {/* Bottom Status Bar */}
      <div className="status-bar">
        <div className="status-item">
          <span className="status-label">Turn:</span>
          <span className="status-value">{sessionState?.turn || 0}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Time:</span>
          <span className="status-value">{sessionState?.time || 'Daytime'}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Weather:</span>
          <span className="status-value">{sessionState?.weather || 'Clear'}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Gold:</span>
          <span className="status-value">
            {sessionState?.gp ?? sessionState?.gold ?? 0} GP
          </span>
        </div>
      </div>
    </div>
  );
};

// CSS for the narrative dashboard
const dashboardCSS = `
.narrative-dashboard {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f0e6d2;
  font-family: 'Georgia', serif;
  color: #333;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background-color: #8B4513;
  color: white;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

.character-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.character-portrait {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: gold;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  border: 2px solid #D4AF37;
}

.character-details h2 {
  margin: 0;
  font-size: 18px;
}

.character-subtitle {
  margin: 5px 0 0 0;
  font-size: 14px;
  opacity: 0.9;
}

.location-info {
  margin: 5px 0 0 0;
  font-size: 12px;
  opacity: 0.8;
}

.dashboard-controls {
  display: flex;
  gap: 10px;
}

.back-button, .settings-button {
  padding: 8px 15px;
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-button:hover, .settings-button:hover, .character-sheet-button:hover, .map-button:hover {
  background-color: rgba(255, 255, 255, 0.3);
}

.dashboard-main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding: 20px;
  flex: 1;
  overflow: hidden;
}

.current-scene-panel {
  background-color: white;
  border: 1px solid #8B4513;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.current-scene-panel h3 {
  color: #8B4513;
  margin-top: 0;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.loading-scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: #666;
}

.loading-spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #8B4513;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.scene-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.scene-description {
  flex: 1;
  padding: 10px;
  background-color: #f9f5f0;
  border: 1px solid #eee;
  border-radius: 4px;
  margin-bottom: 15px;
  overflow-y: auto;
  line-height: 1.6;
}

.quick-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.action-button {
  padding: 8px 12px;
  border: 1px solid #8B4513;
  background-color: white;
  color: #8B4513;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.action-button:hover {
  background-color: #f0e6d2;
}

.action-button.primary {
  background-color: #8B4513;
  color: white;
}

.action-button.primary:hover {
  background-color: #A0522D;
}

.turn-console-section {
  border-top: 1px solid #eee;
  padding-top: 15px;
  margin-top: 15px;
}

.adventure-journal-section {
  height: 100%;
  overflow: hidden;
}

.status-bar {
  background-color: #8B4513;
  color: white;
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.2);
}

.status-item {
  display: flex;
  gap: 5px;
}

.status-label {
  opacity: 0.8;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  position: relative;
}

.modal-close {
  position: absolute;
  top: 10px;
  right: 10px;
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
}
`;

export default NarrativeDashboard;
