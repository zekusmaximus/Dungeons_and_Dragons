import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

interface SessionSummary {
  slug: string;
  world: string;
  updated_at: string;
}

interface PlayerStartProps {
  onBeginWizard: (slug: string) => void;
  onContinue: (slug: string) => void;
  onAdvanced: () => void;
}

const fetchSessions = async (): Promise<SessionSummary[]> => {
  const response = await fetch('/api/sessions');
  if (!response.ok) throw new Error('Failed to load sessions');
  return response.json();
};

const PlayerStart: React.FC<PlayerStartProps> = ({ onBeginWizard, onContinue, onAdvanced }) => {
  const { data: sessions, isLoading } = useQuery({ queryKey: ['sessions'], queryFn: fetchSessions });
  const [adventureName, setAdventureName] = useState('');
  const [template, setTemplate] = useState('example-rogue');
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const sortedSessions = useMemo(
    () => (sessions || []).slice().sort((a, b) => Number(b.updated_at) - Number(a.updated_at)),
    [sessions],
  );

  const handleCreate = async () => {
    setError(null);
    setCreating(true);
    try {
      const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slug: adventureName.trim() || undefined,
          template_slug: template,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Could not start a new adventure');
      }
      onBeginWizard(data.slug);
    } catch (e: any) {
      setError(e.message || 'Unable to start');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="player-start">
      <style>{playerStartCSS}</style>
      <header className="player-start__hero">
        <div className="player-start__titles">
          <p className="eyebrow">Player Mode</p>
          <h1>Sit at the table</h1>
          <p className="lede">
            Step into the world, name your hero, and start chatting with your DM. No mechanics on display—just play.
          </p>
          <div className="hero-actions">
            <button className="primary" onClick={handleCreate} disabled={creating}>
              {creating ? 'Preparing...' : 'Start new adventure'}
            </button>
            <button className="ghost" onClick={onAdvanced}>Advanced</button>
          </div>
          {error && <div className="error">{error}</div>}
        </div>
        <div className="player-start__card">
          <h3>New adventure setup</h3>
          <label>
            Adventure name
            <input
              value={adventureName}
              placeholder="The Ember Road"
              onChange={(e) => setAdventureName(e.target.value)}
            />
          </label>
          <label>
            Template world
            <input
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              placeholder="example-rogue"
            />
          </label>
          <p className="hint">We copy the template world into a fresh session and open the character wizard.</p>
        </div>
      </header>

      <section className="player-start__sessions">
        <div className="section-header">
          <div>
            <p className="eyebrow">Continue</p>
            <h2>Your tables</h2>
          </div>
          <button className="linkish" onClick={() => onBeginWizard(sortedSessions[0]?.slug || '')} disabled={!sortedSessions.length}>
            Skip to wizard with newest
          </button>
        </div>
        {isLoading ? (
          <div className="panel">Loading sessions...</div>
        ) : sortedSessions.length === 0 ? (
          <div className="panel">No saved adventures yet. Start a new one above.</div>
        ) : (
          <div className="session-grid">
            {sortedSessions.map((session) => (
              <button key={session.slug} className="session-card" onClick={() => onContinue(session.slug)}>
                <div className="session-title">{session.slug}</div>
                <div className="session-meta">
                  <span>{session.world}</span>
                  <span>{new Date(Number(session.updated_at) * 1000 || Number(session.updated_at)).toLocaleString()}</span>
                </div>
                <div className="session-cta">Rejoin table</div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

const playerStartCSS = `
.player-start {
  color: #2d1b0b;
  min-height: 100vh;
  background: radial-gradient(circle at 20% 20%, rgba(255,238,209,0.65), transparent 35%),
              radial-gradient(circle at 80% 10%, rgba(205,170,125,0.4), transparent 30%),
              #f7f1e3;
}
.player-start__hero {
  display: grid;
  grid-template-columns: 2fr 1.3fr;
  gap: 24px;
  padding: 48px;
  align-items: start;
}
.player-start__titles h1 {
  margin: 4px 0 8px;
  font-size: 42px;
  letter-spacing: -0.5px;
}
.player-start__titles .lede {
  max-width: 640px;
  margin: 0 0 18px;
  color: #4a2f1b;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 1.2px;
  font-size: 12px;
  color: #8c5a2b;
  margin: 0;
}
.hero-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}
.player-start__card {
  background: #fffaf3;
  border: 1px solid #d9c3a3;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.06);
}
.player-start__card h3 { margin: 0 0 12px; }
.player-start__card label {
  display: flex;
  flex-direction: column;
  font-size: 14px;
  color: #4a2f1b;
  margin-bottom: 10px;
  gap: 4px;
}
.player-start__card input {
  border: 1px solid #c7b090;
  border-radius: 8px;
  padding: 10px;
  font-size: 15px;
  background: #fff;
}
.hint { margin: 6px 0 0; font-size: 12px; color: #6d5138; }
.player-start__sessions {
  padding: 0 48px 48px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.session-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.session-card {
  background: #fff;
  border: 1px solid #d9c3a3;
  border-radius: 10px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  box-shadow: 0 8px 18px rgba(0,0,0,0.05);
}
.session-card:hover { transform: translateY(-2px); box-shadow: 0 12px 24px rgba(0,0,0,0.08); }
.session-title { font-weight: 700; color: #2d1b0b; }
.session-meta { color: #6d5138; font-size: 12px; display: flex; justify-content: space-between; margin-top: 8px; }
.session-cta { margin-top: 10px; font-weight: 600; color: #8c5a2b; }
.panel {
  background: #fffaf3;
  border: 1px dashed #d9c3a3;
  padding: 18px;
  border-radius: 10px;
}
.primary, .ghost, .linkish {
  border-radius: 10px;
  padding: 10px 16px;
  border: 1px solid #b9864c;
  background: #b9864c;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}
.primary:hover { transform: translateY(-1px); box-shadow: 0 8px 14px rgba(0,0,0,0.1); }
.ghost, .linkish {
  background: transparent;
  color: #8c5a2b;
}
.linkish { border: none; padding: 6px 10px; }
.error {
  color: #8c2b1e;
  background: #ffe9e1;
  border: 1px solid #f5c1b5;
  padding: 8px 10px;
  border-radius: 8px;
  margin-top: 12px;
  max-width: 360px;
}
@media (max-width: 900px) {
  .player-start__hero { grid-template-columns: 1fr; padding: 32px 20px; }
  .player-start__sessions { padding: 0 20px 28px; }
}
`;

export default PlayerStart;
