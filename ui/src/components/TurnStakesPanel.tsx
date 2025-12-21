import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

interface TurnStakesPanelProps {
  sessionSlug: string;
  sessionState?: any;
  currentTurn?: { prompt?: string };
  character?: any;
}

interface FactionClock {
  id: string;
  goal: string;
  faction?: string;
  filled?: number;
  segments?: number;
  consequences?: { on_fill?: string; player_facing?: string[] };
}

interface Rumor {
  id: string;
  text: string;
  truth?: string;
  related_factions?: string[];
}

interface Discovery {
  discovery_id: string;
  name: string;
  discovery_type: string;
  description: string;
  location: string;
  importance: number;
}

const TurnStakesPanel: React.FC<TurnStakesPanelProps> = ({
  sessionSlug,
  sessionState,
  currentTurn,
  character,
}) => {
  const turnNumber = sessionState?.turn ?? 0;
  const { data: factionClocks } = useQuery({
    queryKey: ['faction-clocks', sessionSlug],
    queryFn: () =>
      fetch(`/api/sessions/${sessionSlug}/world/faction-clocks`).then((r) => r.json()),
  });

  const { data: rumorsData } = useQuery({
    queryKey: ['rumors', sessionSlug],
    queryFn: () =>
      fetch(`/api/sessions/${sessionSlug}/world/rumors`).then((r) => r.json()),
  });

  const { data: discoveriesData } = useQuery({
    queryKey: ['discoveries', sessionSlug],
    queryFn: () =>
      fetch(`/api/sessions/${sessionSlug}/discoveries/recent?limit=3`).then((r) => r.json()),
  });

  const clocks: FactionClock[] = useMemo(() => {
    if (!factionClocks) return [];
    return Object.values(factionClocks) as FactionClock[];
  }, [factionClocks]);

  const prioritizedClocks = useMemo(() => {
    return clocks
      .slice()
      .sort((a, b) => {
        const aRatio = (a.filled || 0) / (a.segments || 1);
        const bRatio = (b.filled || 0) / (b.segments || 1);
        return bRatio - aRatio;
      })
      .slice(0, 2);
  }, [clocks]);

  const rumors: Rumor[] = useMemo(() => {
    if (!rumorsData) return [];
    return Object.values(rumorsData) as Rumor[];
  }, [rumorsData]);

  const discoveries: Discovery[] = useMemo(() => {
    if (!discoveriesData) return [];
    return discoveriesData as Discovery[];
  }, [discoveriesData]);

  const featuredRumor = rumors.length ? rumors[turnNumber % rumors.length] : null;
  const featuredDiscovery = discoveries.length
    ? discoveries[turnNumber % discoveries.length]
    : null;

  const currentAsk = currentTurn?.prompt?.split('\n')[0] || 'Awaiting the next move.';
  const timeDisplay = sessionState?.time
    ? new Date(sessionState.time).toLocaleString()
    : 'Unknown time';
  const gold = sessionState?.gp ?? sessionState?.gold ?? 0;
  const hp = sessionState?.hp ?? character?.hp ?? '?';
  const location = sessionState?.location || 'Unknown location';

  return (
    <div className="turn-stakes-panel">
      <style>{stakesCSS}</style>
      <div className="stakes-grid">
        <div className="stakes-card">
          <div className="stakes-label">You are here</div>
          <div className="stakes-value">{location}</div>
          <div className="stakes-meta">
            <span>Time: {timeDisplay}</span>
            <span>Weather: {sessionState?.weather || 'n/a'}</span>
          </div>
          <div className="stakes-meta">Prompt: {currentAsk}</div>
        </div>

        <div className="stakes-card">
          <div className="stakes-label">Resources</div>
          <div className="resource-row">
            <span>HP</span>
            <strong>{hp}</strong>
          </div>
          <div className="resource-row">
            <span>Gold</span>
            <strong>{gold} gp</strong>
          </div>
          <div className="resource-row">
            <span>Conditions</span>
            <div className="pill-row">
              {sessionState?.conditions?.length
                ? sessionState.conditions.map((c: string) => (
                    <span key={c} className="pill danger">
                      {c}
                    </span>
                  ))
                : <span className="pill">None</span>}
            </div>
          </div>
        </div>

        <div className="stakes-card">
          <div className="stakes-label">Stakes in motion</div>
          {prioritizedClocks.length ? (
            prioritizedClocks.map((clock) => {
              const progress = Math.round(((clock.filled || 0) / (clock.segments || 1)) * 100);
              return (
                <div key={clock.id} className="clock-row">
                  <div className="clock-header">
                    <strong>{clock.faction || 'Faction clock'}</strong>
                    <span>
                      {clock.filled ?? 0}/{clock.segments ?? '?'}
                    </span>
                  </div>
                  <div className="clock-goal">{clock.goal}</div>
                  <div className="clock-bar">
                    <div className="clock-fill" style={{ width: `${progress}%` }} />
                  </div>
                  {clock.consequences?.player_facing?.length && (
                    <ul className="clock-consequences">
                      {clock.consequences.player_facing.slice(0, 2).map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })
          ) : (
            <div className="placeholder">No active clocks loaded yet.</div>
          )}
        </div>
      </div>

      <div className="stakes-grid narrow">
        <div className="stakes-card">
          <div className="stakes-label">Discovery drip</div>
          {featuredDiscovery ? (
            <>
              <div className="pill subtle">{featuredDiscovery.discovery_type}</div>
              <div className="stakes-value">{featuredDiscovery.name}</div>
              <div className="stakes-meta">{featuredDiscovery.description}</div>
              <div className="stakes-meta">Location: {featuredDiscovery.location}</div>
            </>
          ) : (
            <div className="placeholder">Discoveries will appear as you log them.</div>
          )}
        </div>
        <div className="stakes-card">
          <div className="stakes-label">Rumor to chase</div>
          {featuredRumor ? (
            <>
              <div className="stakes-value">{featuredRumor.text}</div>
              <div className="stakes-meta">
                Truth: {featuredRumor.truth || 'unknown'} • Factions:{' '}
                {featuredRumor.related_factions?.join(', ') || '—'}
              </div>
            </>
          ) : (
            <div className="placeholder">Rumors will surface from your world data.</div>
          )}
        </div>
      </div>
    </div>
  );
};

const stakesCSS = `
.turn-stakes-panel {
  margin-bottom: 12px;
  font-family: 'Georgia', serif;
}

.stakes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}

.stakes-grid.narrow {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.stakes-card {
  background: #fff7ec;
  border: 1px solid #d7b892;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.stakes-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  color: #8B4513;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.stakes-value {
  font-weight: 700;
  font-size: 16px;
  margin-bottom: 4px;
}

.stakes-meta {
  font-size: 12px;
  color: #4a4a4a;
  margin-bottom: 4px;
}

.resource-row, .clock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 13px;
}

.pill-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.pill {
  background: #ede1d0;
  color: #5a4633;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  border: 1px solid #d7b892;
}

.pill.danger {
  background: #ffe3e0;
  border-color: #e57373;
  color: #b23b3b;
}

.pill.subtle {
  background: #f0e6d2;
}

.clock-row {
  margin-bottom: 10px;
  padding: 8px;
  background: #fff;
  border: 1px dashed #d7b892;
  border-radius: 6px;
}

.clock-goal {
  font-size: 12px;
  color: #555;
  margin-bottom: 6px;
}

.clock-bar {
  background: #f5e6d3;
  border-radius: 6px;
  height: 8px;
  overflow: hidden;
  margin-bottom: 6px;
}

.clock-fill {
  height: 8px;
  background: linear-gradient(90deg, #8B4513, #d4883c);
}

.clock-consequences {
  margin: 0;
  padding-left: 16px;
  color: #444;
  font-size: 12px;
}

.placeholder {
  color: #7a6c5a;
  font-size: 12px;
  font-style: italic;
}
`;

export default TurnStakesPanel;
