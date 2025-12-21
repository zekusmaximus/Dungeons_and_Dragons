import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

interface SessionSummary {
   slug: string;
   world: string;
   has_lock: boolean;
   updated_at: string;
}

interface AdventureHook {
  hook_id: string;
  title: string;
  description: string;
  hook_type: string;
  location: string;
  difficulty: string;
}

const fetchSessions = async (): Promise<SessionSummary[]> => {
  const response = await fetch('/api/sessions');
  if (!response.ok) throw new Error('Failed to fetch sessions');
  return response.json();
};

const fetchAdventureHooks = async (): Promise<AdventureHook[]> => {
  const response = await fetch('/api/adventure-hooks/recommended');
  if (!response.ok) throw new Error('Failed to fetch adventure hooks');
  return response.json();
};

interface LobbyProps {
  onSelectSession: (slug: string) => void;
  onNewAdventure: (hookId: string) => void | Promise<void>;
}

const Lobby: React.FC<LobbyProps> = ({ onSelectSession, onNewAdventure }) => {
  const { data: sessions, isLoading: isSessionsLoading, error: sessionsError } = useQuery({
    queryKey: ['sessions'],
    queryFn: fetchSessions,
  });

  const { data: adventureHooks, isLoading: isHooksLoading, error: hooksError } = useQuery({
    queryKey: ['adventure-hooks'],
    queryFn: fetchAdventureHooks,
  });

  const [activeTab, setActiveTab] = useState<'sessions' | 'new-adventure'>('sessions');
  const [selectedHook, setSelectedHook] = useState<string | null>(null);

  if (isSessionsLoading || isHooksLoading) return (
    <div className="lobby-container">
      <div className="loading-message">Loading your adventures...</div>
    </div>
  );

  if (sessionsError || hooksError) return (
    <div className="lobby-container">
      <div className="error-message">Error loading data. Please refresh.</div>
    </div>
  );

  return (
    <div className="lobby-container">
      <style>{lobbyCSS}</style>

      <div className="lobby-header">
        <h1>🏰 D&D Solo Adventure Lobby</h1>
        <p className="welcome-message">Welcome, brave adventurer! Choose your path...</p>
      </div>

      <div className="lobby-tabs">
        <button
          onClick={() => setActiveTab('sessions')}
          className={`tab-button ${activeTab === 'sessions' ? 'active' : ''}`}
        >
          ✨ Continue Adventure
        </button>
        <button
          onClick={() => setActiveTab('new-adventure')}
          className={`tab-button ${activeTab === 'new-adventure' ? 'active' : ''}`}
        >
          ⚔️ New Adventure
        </button>
      </div>

      {activeTab === 'sessions' ? (
        <div className="sessions-list">
          <h2>Your Adventures</h2>
          {sessions && sessions.length > 0 ? (
            <ul className="session-items">
              {sessions.map((session) => (
                <li key={session.slug} className="session-item">
                  <button 
                    onClick={() => onSelectSession(session.slug)}
                    className="session-button"
                  >
                    <span className="session-name">{session.slug}</span>
                    <span className="session-world">🌍 {session.world}</span>
                    <span className="session-status">
                      {session.has_lock ? '🔒 Locked' : '🔓 Available'}
                    </span>
                    <span className="session-updated">
                      ⏰ {new Date(session.updated_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="no-sessions">
              <p>No existing adventures found.</p>
              <p>Start a new adventure to begin your journey!</p>
            </div>
          )}
        </div>
      ) : (
        <div className="new-adventure-section">
          <h2>Begin a New Adventure</h2>
          <p className="adventure-intro">
            Choose an adventure hook to start your solo journey. Each hook offers a unique 
            starting point for your epic tale!
          </p>

          <div className="adventure-hooks">
            {adventureHooks && adventureHooks.length > 0 ? (
              <div className="hooks-grid">
                {adventureHooks.map((hook) => (
                  <div 
                    key={hook.hook_id} 
                    className={`hook-card ${selectedHook === hook.hook_id ? 'selected' : ''}`}
                    onClick={() => setSelectedHook(hook.hook_id)}
                  >
                    <h3 className="hook-title">{hook.title}</h3>
                    <div className="hook-meta">
                      <span className={`difficulty-badge ${hook.difficulty}`}>{hook.difficulty}</span>
                      <span className="location-badge">📍 {hook.location}</span>
                    </div>
                    <p className="hook-description">{hook.description}</p>
                    <div className="hook-type">
                      <span className="type-badge">{hook.hook_type}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-hooks">
                <p>No adventure hooks available.</p>
                <p>Please check your connection and try again.</p>
              </div>
            )}
          </div>

          {selectedHook && (
            <div className="adventure-start">
              <button
                onClick={() => onNewAdventure(selectedHook)}
                className="start-adventure-button"
              >
                🚀 Begin Adventure!
              </button>
              <p className="adventure-note">
                Your epic journey awaits! Click the button above to start your adventure.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// CSS for the enhanced lobby
const lobbyCSS = `
.lobby-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Georgia', serif;
  color: #333;
}

.lobby-header {
  text-align: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #8B4513;
}

.lobby-header h1 {
  color: #8B4513;
  margin: 0;
  font-size: 28px;
}

.welcome-message {
  font-size: 16px;
  color: #666;
  margin: 10px 0 0 0;
}

.lobby-tabs {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
  gap: 10px;
}

.tab-button {
  padding: 12px 24px;
  background-color: #f0e6d2;
  border: 2px solid #8B4513;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  font-weight: bold;
  transition: all 0.2s;
  color: #8B4513;
}

.tab-button:hover {
  background-color: #e8d8c0;
}

.tab-button.active {
  background-color: #8B4513;
  color: white;
}

.sessions-list h2,
.new-adventure-section h2 {
  color: #8B4513;
  margin-bottom: 15px;
  font-size: 22px;
}

.session-items {
  list-style: none;
  padding: 0;
  margin: 0;
}

.session-item {
  margin-bottom: 12px;
}

.session-button {
  width: 100%;
  padding: 15px;
  background-color: white;
  border: 2px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.session-button:hover {
  border-color: #8B4513;
  background-color: #f9f5f0;
}

.session-name {
  font-weight: bold;
  color: #8B4513;
  font-size: 16px;
}

.session-world {
  color: #666;
  font-size: 14px;
}

.session-status {
  font-size: 14px;
}

.session-updated {
  font-size: 12px;
  color: #999;
}

.no-sessions {
  text-align: center;
  padding: 30px;
  color: #666;
  font-style: italic;
}

.adventure-intro {
  margin-bottom: 20px;
  color: #666;
  line-height: 1.6;
}

.hooks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.hook-card {
  border: 2px solid #ddd;
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.2s;
  background-color: white;
}

.hook-card:hover {
  border-color: #8B4513;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.hook-card.selected {
  border-color: #4CAF50;
  background-color: #f0fff0;
}

.hook-title {
  margin: 0 0 10px 0;
  color: #8B4513;
  font-size: 18px;
}

.hook-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.difficulty-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  color: white;
}

.difficulty-badge.easy {
  background-color: #81C784;
}

.difficulty-badge.medium {
  background-color: #FFB74D;
}

.difficulty-badge.hard {
  background-color: #E57373;
}

.difficulty-badge.epic {
  background-color: #9C27B0;
}

.location-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  background-color: #4FC3F7;
  color: white;
}

.hook-description {
  margin: 10px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.4;
}

.type-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  background-color: #9E9E9E;
  color: white;
}

.adventure-start {
  text-align: center;
  margin-top: 20px;
}

.start-adventure-button {
  padding: 15px 30px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
}

.start-adventure-button:hover {
  background-color: #45a049;
  transform: scale(1.05);
}

.adventure-note {
  margin-top: 15px;
  color: #666;
  font-style: italic;
}

.no-hooks {
  text-align: center;
  padding: 30px;
  color: #666;
  font-style: italic;
}

.loading-message,
.error-message {
  text-align: center;
  padding: 50px;
  font-size: 16px;
}

.loading-message {
  color: #8B4513;
}

.error-message {
  color: #E57373;
}
`;

export default Lobby;
