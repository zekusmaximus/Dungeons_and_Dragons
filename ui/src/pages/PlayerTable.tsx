import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

interface AbilityBlock {
  str?: number;
  dex?: number;
  con?: number;
  int?: number;
  wis?: number;
  cha?: number;
}

interface DMChoice {
  text: string;
  intent_tag: string;
  risk: string;
}

interface DMNarration {
  narration: string;
  recap: string;
  stakes: string;
  choices: DMChoice[];
  consequence_echo?: string;
  discovery_added?: { title: string; text: string };
  roll_request?: RollRequest;
}

interface TurnRecord {
  turn: number;
  player_intent: string;
  diff: string[];
  consequence_echo: string;
  dm: DMNarration;
  created_at: string;
}

interface PlayerBundle {
  state: any;
  character: any;
  recaps: TurnRecord[];
  discoveries: { name: string; description: string; discovery_type: string }[];
  quests: Record<string, any>;
  suggestions: string[];
}

interface PlayerTurnResponse {
  state: any;
  narration: DMNarration;
  turn_record: TurnRecord;
  suggestions: string[];
  roll_request?: RollRequest;
}

interface PlayerTableProps {
  sessionSlug: string;
  onBack: () => void;
  onAdvanced: () => void;
}

type ChatMessage = { role: 'dm' | 'player'; text: string; recap?: string; stakes?: string };

type RollType = 'ability_check' | 'saving_throw' | 'attack' | 'damage' | 'initiative';
type AdvantageType = 'advantage' | 'disadvantage' | 'normal' | undefined;

interface RollRequest {
  type: RollType;
  ability?: 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
  skill?: string;
  dc?: number;
  advantage?: AdvantageType;
  notes?: string;
}

interface RollResult {
  total: number;
  rolls: number[];
  modifier: number;
  label: string;
}

const fetchBundle = async (slug: string): Promise<PlayerBundle> => {
  const response = await fetch(`/api/sessions/${slug}/player`);
  if (!response.ok) throw new Error('Failed to load table');
  return response.json();
};

const PlayerTable: React.FC<PlayerTableProps> = ({ sessionSlug, onBack, onAdvanced }) => {
  const queryClient = useQueryClient();
  const { data: bundle, refetch, isFetching } = useQuery({
    queryKey: ['player-bundle', sessionSlug],
    queryFn: () => fetchBundle(sessionSlug),
  });
  const [input, setInput] = useState('');
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [rollRequest, setRollRequest] = useState<RollRequest | null>(null);
  const [rollResult, setRollResult] = useState<RollResult | null>(null);

  useEffect(() => {
    setChat([]);
    setInput('');
    setRollRequest(null);
    setRollResult(null);
  }, [sessionSlug]);

  useEffect(() => {
    if (!bundle) return;
    const seeded: ChatMessage[] = [];
    const reversed = [...(bundle.recaps || [])].reverse();
    reversed.forEach((record) => {
      const intent = record.player_intent?.trim();
      if (intent && intent.toLowerCase() !== 'opening scene') {
        seeded.push({ role: 'player', text: intent });
      }
      seeded.push({
        role: 'dm',
        text: record.dm?.narration || '',
        recap: record.dm?.recap,
        stakes: record.dm?.stakes,
      });
    });
    setChat((prev) => (prev.length ? prev : seeded));
    setSuggestions(bundle.suggestions || []);
    const latestRoll = bundle.recaps?.[0]?.dm?.roll_request;
    setRollRequest(latestRoll || null);
  }, [bundle, sessionSlug]);

  const abilityBlock: AbilityBlock = useMemo(() => {
    const raw = bundle?.character?.abilities || bundle?.state?.abilities || {};
    return {
      str: raw.str ?? raw.str_ ?? raw.STR,
      dex: raw.dex ?? raw.DEX,
      con: raw.con ?? raw.CON,
      int: raw.int ?? raw.int_ ?? raw.INT,
      wis: raw.wis ?? raw.WIS,
      cha: raw.cha ?? raw.CHA,
    };
  }, [bundle]);

  const abilityMod = (score?: number) => (typeof score === 'number' ? Math.floor((score - 10) / 2) : 0);

  const formatRollLabel = (req: RollRequest) => {
    const parts = [];
    if (req.type === 'ability_check') parts.push('Ability check');
    if (req.type === 'saving_throw') parts.push('Saving throw');
    if (req.type === 'attack') parts.push('Attack roll');
    if (req.type === 'damage') parts.push('Damage roll');
    if (req.type === 'initiative') parts.push('Initiative');
    if (req.skill) parts.push(req.skill);
    if (req.ability) parts.push(`(${req.ability})`);
    if (req.advantage && req.advantage !== 'normal') parts.push(req.advantage);
    if (typeof req.dc === 'number') parts.push(`DC ${req.dc}`);
    return parts.join(' ');
  };

  const handleRoll = async () => {
    if (!rollRequest) return;
    setError(null);
    try {
      const response = await fetch(`/api/sessions/${sessionSlug}/player/roll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rollRequest),
      });
      const data: RollResult = await response.json();
      if (!response.ok) {
        throw new Error((data as any).detail);
      }
      setRollResult(data);
      const modText = data.modifier ? ` ${data.modifier >= 0 ? '+' : '-'} ${Math.abs(data.modifier)}` : '';
      const baseText = `${data.rolls.join('/')} ${modText}`.trim();
      const fill = `I roll ${data.label}: ${baseText} = ${data.total}`;
      setInput(fill);
    } catch (e: any) {
      setError('The DM couldn’t respond. Check your LLM settings.');
    }
  };

  const sendAction = async () => {
    if (!input.trim()) return;
    setSending(true);
    setError(null);
    const actionText = input.trim();
    setChat((prev) => [...prev, { role: 'player', text: actionText }]);
    try {
      const response = await fetch(`/api/sessions/${sessionSlug}/player/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionText }),
      });
      const data: PlayerTurnResponse = await response.json();
      if (!response.ok) {
        throw new Error((data as any).detail || 'The DM could not respond yet.');
      }
      setChat((prev) => [
        ...prev,
        {
          role: 'dm',
          text: data.narration.narration,
          recap: data.narration.recap,
          stakes: data.narration.stakes,
        },
      ]);
      setSuggestions(data.suggestions || []);
      setInput('');
      setRollRequest(data.roll_request || data.narration?.roll_request || null);
      setRollResult(null);
      queryClient.invalidateQueries({ queryKey: ['player-bundle', sessionSlug] });
      refetch();
    } catch (e: any) {
      setError('The DM couldn’t respond. Check your LLM settings.');
    } finally {
      setSending(false);
    }
  };

  const displaySuggestions = suggestions.length ? suggestions.slice(0, 5) : [
    'Survey the area for clues',
    'Talk to someone nearby',
    'Check your gear',
    'Look for tracks or markings',
    'Pause to plan',
  ];

  return (
    <div className="player-table">
      <style>{tableCSS}</style>
      <header className="table-header">
        <div>
          <p className="eyebrow">Session</p>
          <h2>{bundle?.character?.name || 'Adventurer'} at the table</h2>
          <p className="subtle">{bundle?.state?.location || 'Unknown location'} • Turn {bundle?.state?.turn ?? 0}</p>
        </div>
        <div className="header-actions">
          <button className="ghost" onClick={onBack}>Back to start</button>
          <button className="linkish" onClick={onAdvanced}>Advanced</button>
        </div>
      </header>

      <main className="table-layout">
        <section className="chat">
          <div className="chat-feed">
            {chat.length === 0 && <div className="panel">No turns yet. Tell the DM what you do.</div>}
            {chat.map((msg, idx) => (
              <div key={idx} className={`chat-line ${msg.role}`}>
                <div className="chat-label">{msg.role === 'dm' ? 'DM' : 'You'}</div>
                <div className="chat-text">{msg.text}</div>
                {msg.recap && <div className="chat-recap">{msg.recap}</div>}
                {msg.stakes && <div className="chat-stakes">Stakes: {msg.stakes}</div>}
              </div>
            ))}
          </div>
          {rollRequest && (
            <div className="roll-panel">
              <div>
                <div className="roll-title">Roll requested</div>
                <div className="roll-desc">{formatRollLabel(rollRequest)}</div>
                {rollRequest.notes && <div className="subtle">{rollRequest.notes}</div>}
              </div>
              <div className="roll-actions">
                <button className="primary" onClick={handleRoll}>Roll</button>
                {typeof rollRequest.dc === 'number' && <div className="dc-pill">DC {rollRequest.dc}</div>}
              </div>
              {rollResult && (
                <div className="roll-result">
                  Result: {rollResult.total} (rolls {rollResult.rolls.join('/')} {rollResult.modifier ? `${rollResult.modifier >= 0 ? '+' : '-'}${Math.abs(rollResult.modifier)}` : ''})
                </div>
              )}
            </div>
          )}
          <div className="composer">
            <label>What do you do?</label>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Describe your move, ask a question, or try something bold."
              rows={3}
            />
            <div className="composer-actions">
              <div className="suggestions">
                <div className="suggestions-label">Suggestions (you can do anything):</div>
                <div className="suggestion-chips">
                  {displaySuggestions.slice(0, 5).map((suggestion) => (
                    <button key={suggestion} onClick={() => setInput(suggestion)}>{suggestion}</button>
                  ))}
                </div>
              </div>
              <button className="primary" onClick={sendAction} disabled={sending}>{sending ? 'Sending...' : 'Send'}</button>
            </div>
            {error && <div className="error">{error}</div>}
            {isFetching && <div className="subtle">Refreshing table...</div>}
          </div>
        </section>

        <aside className="sidebar">
          <div className="card">
            <div className="card-header">
              <div>
                <h3>Character</h3>
                <p className="subtle">{bundle?.character?.race || bundle?.character?.ancestry || 'Unknown'}</p>
              </div>
              <div className="stat">
                <div className="label">AC</div>
                <div className="value">{bundle?.state?.ac ?? bundle?.character?.ac ?? '-'}</div>
              </div>
              <div className="stat">
                <div className="label">HP</div>
                <div className="value">
                  {bundle?.state?.hp ?? '-'}{bundle?.state?.max_hp ? ` / ${bundle?.state?.max_hp}` : ''}
                </div>
              </div>
            </div>
            <div className="abilities-grid">
              {abilityKeys.map((key) => (
                <div key={key} className="ability-pill">
                  <div className="label">{key.toUpperCase()}</div>
                  <div className="value">{abilityBlock[key]}</div>
                  <div className="subtle">Mod {abilityMod(abilityBlock[key]) >= 0 ? '+' : ''}{abilityMod(abilityBlock[key])}</div>
                </div>
              ))}
            </div>
            <div className="section">
              <h4>Inventory</h4>
              <ul>
                {(bundle?.state?.inventory || bundle?.character?.inventory || []).map((item: string) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="section">
              <h4>Spells</h4>
              {bundle?.state?.spells || bundle?.character?.spells ? (
                <ul>
                  {(bundle?.state?.spells || bundle?.character?.spells || []).map((spell: string) => (
                    <li key={spell}>{spell}</li>
                  ))}
                </ul>
              ) : (
                <p className="subtle">No spells recorded.</p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Journal</h3>
            </div>
            <div className="section">
              <h4>Adventure hook</h4>
              <p>{bundle?.state?.adventure_hook?.label || 'Not set yet.'}</p>
            </div>
            <div className="section">
              <h4>Last recap</h4>
              <p>{bundle?.recaps?.[0]?.dm?.recap || 'No recap yet.'}</p>
            </div>
            <div className="section">
              <h4>Quests</h4>
              {bundle?.quests && Object.keys(bundle.quests).length > 0 ? (
                <ul>
                  {Object.values(bundle.quests).map((quest: any) => (
                    <li key={quest.id || quest.name || quest.title}>
                      <strong>{quest.title || quest.name || quest.id}</strong>
                      {quest.status && <span className="subtle"> · {quest.status}</span>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="subtle">No active quests.</p>
              )}
            </div>
            <div className="section">
              <h4>Discoveries & Rumors</h4>
              {bundle?.discoveries && bundle.discoveries.length > 0 ? (
                <ul>
                  {bundle.discoveries.map((disc) => (
                    <li key={disc.name + disc.discovery_type}>
                      <strong>{disc.name || disc.discovery_type}</strong>
                      {disc.description && <div className="subtle">{disc.description}</div>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="subtle">Nothing noted yet.</p>
              )}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
};

const tableCSS = `
.player-table {
  background: radial-gradient(circle at 10% 20%, rgba(255,238,209,0.7), transparent 25%),
              radial-gradient(circle at 80% 0%, rgba(205,170,125,0.35), transparent 22%),
              #f7f1e3;
  min-height: 100vh;
  padding: 28px 32px 80px;
  color: #2d1b0b;
}
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.subtle { color: #6d5138; font-size: 13px; margin: 0; }
.header-actions { display: flex; gap: 10px; }
.table-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-top: 16px;
}
.chat {
  background: #fff;
  border: 1px solid #d9c3a3;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chat-feed {
  max-height: 60vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chat-line {
  padding: 10px;
  border-radius: 10px;
  background: #fffaf3;
  border: 1px solid #ecd7b6;
}
.chat-line.dm { border-color: #c19a6b; }
.chat-label { font-weight: 700; color: #8c5a2b; }
.chat-text { margin: 4px 0; }
.chat-recap { color: #4a2f1b; font-size: 13px; }
.chat-stakes { color: #8c5a2b; font-size: 12px; }
.roll-panel {
  border: 1px solid #d9c3a3;
  border-radius: 12px;
  padding: 12px;
  background: #fffaf3;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.roll-title { font-weight: 700; color: #2d1b0b; }
.roll-desc { color: #4a2f1b; }
.roll-actions { display: flex; align-items: center; gap: 10px; }
.dc-pill {
  padding: 6px 10px;
  border-radius: 12px;
  background: #ede0c8;
  color: #2d1b0b;
  font-weight: 700;
}
.roll-result { color: #2d1b0b; font-weight: 600; }
.composer label { font-weight: 700; }
.composer textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid #c7b090;
  padding: 12px;
  background: #fffaf3;
  font-size: 15px;
}
.composer-actions {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.suggestions { flex: 1; }
.suggestions-label { font-size: 12px; color: #6d5138; margin-bottom: 6px; }
.suggestion-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.suggestion-chips button {
  border-radius: 20px;
  border: 1px solid #d9c3a3;
  padding: 8px 12px;
  background: #fff;
  cursor: pointer;
}
.primary, .ghost, .linkish {
  border-radius: 10px;
  padding: 10px 16px;
  border: 1px solid #b9864c;
  font-weight: 700;
  cursor: pointer;
}
.primary { background: #b9864c; color: #fff; }
.ghost, .linkish { background: transparent; color: #8c5a2b; }
.linkish { border: none; }
.sidebar { display: flex; flex-direction: column; gap: 14px; }
.card {
  background: #fff;
  border: 1px solid #d9c3a3;
  border-radius: 14px;
  padding: 14px;
  box-shadow: 0 12px 24px rgba(0,0,0,0.04);
}
.card-header { display: flex; align-items: center; gap: 10px; }
.stat { background: #fffaf3; border: 1px solid #ecd7b6; border-radius: 10px; padding: 6px 10px; }
.stat .label { font-size: 12px; color: #6d5138; }
.stat .value { font-weight: 800; color: #2d1b0b; }
.abilities-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 8px;
  margin-top: 10px;
}
.ability-pill {
  border: 1px solid #d9c3a3;
  border-radius: 10px;
  padding: 8px;
  text-align: center;
  background: #fffaf3;
}
.section { margin-top: 10px; }
.section h4 { margin: 0 0 6px; }
.section ul { padding-left: 16px; margin: 0; color: #2d1b0b; }
.panel {
  background: #fffaf3;
  border: 1px dashed #d9c3a3;
  padding: 12px;
  border-radius: 10px;
}
.error {
  color: #8c2b1e;
  background: #ffe9e1;
  border: 1px solid #f5c1b5;
  padding: 8px 10px;
  border-radius: 8px;
  margin-top: 8px;
}
@media (max-width: 1000px) {
  .table-layout { grid-template-columns: 1fr; }
  .chat-feed { max-height: none; }
}
`;

export default PlayerTable;
