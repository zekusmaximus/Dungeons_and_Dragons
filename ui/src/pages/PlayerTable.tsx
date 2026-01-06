import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import LiveUpdates from '../components/LiveUpdates';

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
  rolls?: { total: number; breakdown: string; text: string }[];
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

type ChatMessage = { role: 'dm' | 'player' | 'roll' | 'log'; text: string; recap?: string; stakes?: string };

type RollType = 'ability_check' | 'saving_throw' | 'attack' | 'damage' | 'initiative';
type AdvantageType = 'advantage' | 'disadvantage' | 'normal' | undefined;

interface RollRequest {
  kind: RollType;
  ability?: 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
  skill?: string;
  dc?: number;
  advantage?: AdvantageType;
  reason?: string;
}

interface RollResult {
  d20: number[];
  total: number;
  breakdown: string;
  text: string;
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
  const [retryAction, setRetryAction] = useState<string | null>(null);
  const [isCharacterOpen, setIsCharacterOpen] = useState(true);
  const [isJournalOpen, setIsJournalOpen] = useState(true);
  const [liveLines, setLiveLines] = useState<string[]>([]);
  const [liveChangelog, setLiveChangelog] = useState<string[]>([]);
  const [liveRolls, setLiveRolls] = useState<{ turn: number; items: any[] } | null>(null);
  const transcriptSeenRef = useRef<string[]>([]);

  useEffect(() => {
    setChat([]);
    setInput('');
    setRollRequest(null);
    setRollResult(null);
    setLiveLines([]);
    setLiveChangelog([]);
    setLiveRolls(null);
    transcriptSeenRef.current = [];
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
      if (record.rolls?.length) {
        record.rolls.forEach((roll) => {
          seeded.push({ role: 'roll', text: formatRollSummary(roll.total, roll.breakdown) });
        });
      }
    });
    setChat((prev) => (prev.length ? prev : seeded));
    setSuggestions(bundle.suggestions || []);
    const latestRoll = bundle.recaps?.[0]?.dm?.roll_request;
    setRollRequest(latestRoll || null);
  }, [bundle, sessionSlug]);

  useEffect(() => {
    if (!liveLines.length) return;
    const newLines = liveLines.filter((line) => !transcriptSeenRef.current.includes(line));
    if (!newLines.length) return;
    transcriptSeenRef.current.push(...newLines);
    setChat((prev) => [...prev, ...newLines.map((text) => ({ role: 'dm' as const, text }))]);
  }, [liveLines]);

  useEffect(() => {
    if (!liveChangelog.length) return;
    setChat((prev) => [...prev, ...liveChangelog.map((text) => ({ role: 'log' as const, text }))]);
  }, [liveChangelog]);

  useEffect(() => {
    if (!liveRolls || !liveRolls.items?.length) return;
    setChat((prev) => [
      ...prev,
      ...liveRolls.items.map((roll) => ({
        role: 'roll' as const,
        text: formatRollSummary(roll.total, roll.breakdown || roll.text || ''),
      })),
    ]);
  }, [liveRolls]);

  useEffect(() => {
    if (!rollRequest) {
      setRollResult(null);
    }
  }, [rollRequest]);

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

  const abilityKeys: (keyof AbilityBlock)[] = ['str', 'dex', 'con', 'int', 'wis', 'cha'];

  const abilityMod = (score?: number) => (typeof score === 'number' ? Math.floor((score - 10) / 2) : 0);

  const abilityNames: Record<string, string> = {
    STR: 'Strength',
    DEX: 'Dexterity',
    CON: 'Constitution',
    INT: 'Intelligence',
    WIS: 'Wisdom',
    CHA: 'Charisma',
  };

  const skillToAbility: Record<string, string> = {
    athletics: 'STR',
    acrobatics: 'DEX',
    stealth: 'DEX',
    sleight: 'DEX',
    investigation: 'INT',
    arcana: 'INT',
    history: 'INT',
    nature: 'INT',
    religion: 'INT',
    perception: 'WIS',
    insight: 'WIS',
    survival: 'WIS',
    medicine: 'WIS',
    animal: 'WIS',
    persuasion: 'CHA',
    deception: 'CHA',
    intimidation: 'CHA',
    performance: 'CHA',
  };

  const titleCase = (value?: string) => (value ? value.replace(/\w\S*/g, (word) => word[0].toUpperCase() + word.slice(1).toLowerCase()) : '');
  const shorten = (value?: string, max = 120) => {
    if (!value) return '';
    const compact = value.replace(/\s+/g, ' ').trim();
    if (compact.length <= max) return compact;
    return `${compact.slice(0, max - 1)}...`;
  };

  const formatRollRequest = (req: RollRequest) => {
    const skill = req.skill ? titleCase(req.skill.replace(/_/g, ' ')) : '';
    const inferredAbility = req.ability || (req.skill ? skillToAbility[req.skill.toLowerCase().split(' ')[0]] : undefined);
    const abilityLabel = inferredAbility ? abilityNames[inferredAbility] : '';
    let base = 'Roll';

    if (req.kind === 'ability_check') {
      if (abilityLabel && skill) base = `Roll a ${abilityLabel} (${skill}) check.`;
      else if (abilityLabel) base = `Roll a ${abilityLabel} check.`;
      else if (skill) base = `Roll a ${skill} check.`;
      else base = 'Roll a check.';
    } else if (req.kind === 'saving_throw') {
      base = abilityLabel ? `Roll a ${abilityLabel} saving throw.` : 'Roll a saving throw.';
    } else if (req.kind === 'attack') {
      base = 'Roll an attack roll.';
    } else if (req.kind === 'damage') {
      base = 'Roll damage.';
    } else if (req.kind === 'initiative') {
      base = 'Roll initiative.';
    }

    if (req.advantage && req.advantage !== 'normal') {
      base = `${base.replace(/\.$/, '')} with ${req.advantage}.`;
    }

    return base;
  };

  const formatRollSummary = (total: number, breakdown: string) => {
    const normalized = breakdown
      .replace(/\s*\(([^)]+)\)/g, ' $1')
      .replace(/\s+/g, ' ')
      .trim();
    return `Result: ${total} (${normalized})`;
  };

  const formatRollResult = (result: RollResult) => formatRollSummary(result.total, result.breakdown);

  const handleRoll = async () => {
    if (!rollRequest) return;
    setError(null);
    try {
      const response = await fetch(`/api/sessions/${sessionSlug}/roll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: rollRequest.kind,
          ability: rollRequest.ability,
          skill: rollRequest.skill,
          advantage: rollRequest.advantage,
        }),
      });
      const data: RollResult = await response.json();
      if (!response.ok) {
        throw new Error((data as any).detail);
      }
      setRollResult(data);
      const formatted = formatRollResult(data);
      setInput(formatted);
      setChat((prev) => [...prev, { role: 'roll', text: formatted }]);
    } catch (e: any) {
      setError('The DM gestures for a pause. Try again in a moment.');
    }
  };

  const handleRollAndSend = async () => {
    if (!rollRequest || sending) return;
    setError(null);
    try {
      const response = await fetch(`/api/sessions/${sessionSlug}/roll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: rollRequest.kind,
          ability: rollRequest.ability,
          skill: rollRequest.skill,
          advantage: rollRequest.advantage,
        }),
      });
      const data: RollResult = await response.json();
      if (!response.ok) {
        throw new Error((data as any).detail);
      }
      setRollResult(data);
      const formatted = formatRollResult(data);
      setInput(formatted);
      setChat((prev) => [...prev, { role: 'roll', text: formatted }]);
      await sendAction(formatted);
    } catch (e: any) {
      setError('The DM gestures for a pause. Try again in a moment.');
    }
  };

  const sendAction = async (override?: string) => {
    const actionText = (override ?? input).trim();
    if (!actionText) return;
    setSending(true);
    setError(null);
    setRetryAction(null);
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
        { role: 'player', text: actionText },
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
      setRetryAction(actionText);
      setError('The DM raises a hand mid-sentence. Give it a breath, then try again.');
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!rollRequest) return;
      if (event.key !== 'r' && event.key !== 'R') return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.isContentEditable)) {
        return;
      }
      event.preventDefault();
      handleRollAndSend();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [rollRequest, handleRollAndSend]);

  const displaySuggestions = suggestions.length ? suggestions.slice(0, 5) : [
    'Survey the area for clues',
    'Talk to someone nearby',
    'Check your gear',
    'Look for tracks or markings',
    'Pause to plan',
  ];

  const characterName = bundle?.character?.name || 'Adventurer';
  const characterClass = bundle?.character?.class || bundle?.character?.class_name || bundle?.character?.className || 'Wanderer';
  const location = bundle?.state?.location || 'Unknown location';
  const hpCurrent = bundle?.state?.hp ?? bundle?.character?.hp ?? '-';
  const hpMax = bundle?.state?.max_hp ?? bundle?.character?.max_hp;
  const acValue = bundle?.state?.ac ?? bundle?.character?.ac ?? '-';
  const hpLabel = hpMax ? `${hpCurrent} / ${hpMax}` : `${hpCurrent}`;
  const questList = bundle?.quests ? Object.values(bundle.quests) : [];
  const activeQuests = questList.filter((quest: any) => {
    const status = (quest?.status || '').toString().toLowerCase();
    return !status || !['done', 'complete', 'completed', 'resolved', 'closed'].includes(status);
  });
  const primaryQuest = activeQuests[0];
  const questObjective = Array.isArray(primaryQuest?.objectives) ? primaryQuest.objectives[0] : primaryQuest?.objective;
  const objective = shorten(questObjective || primaryQuest?.title || primaryQuest?.name || primaryQuest?.id || bundle?.state?.adventure_hook?.label, 100);
  const rollPrompt = rollRequest ? formatRollRequest(rollRequest).replace(/\.$/, '') : '';
  const pressure = shorten(
    rollRequest
      ? `Pending roll: ${rollRequest.reason || rollPrompt}`
      : bundle?.recaps?.[0]?.consequence_echo,
    120,
  );
  const line1Parts = [];
  if (objective) line1Parts.push(`Objective: ${objective}`);
  if (pressure) line1Parts.push(`Pressure: ${pressure}`);
  let stakesLine1 = line1Parts.join('  ');
  let stakesLine2 = location ? `Location: ${shorten(location, 80)}` : '';
  if (!stakesLine1 && location) {
    stakesLine1 = `Location: ${shorten(location, 80)}`;
    stakesLine2 = '';
  }
  const inputPlaceholder = rollRequest
    ? 'Roll pending - click Roll & Send or type the result.'
    : 'Describe your move, ask a question, or try something bold.';
  const npcMemory = (bundle?.state?.npc_memory || bundle?.state?.npcs || bundle?.state?.npcMemory || []) as any[];
  const keyNpcs = Array.isArray(npcMemory) ? npcMemory.slice(0, 3) : [];
  const hookLabel = bundle?.state?.adventure_hook?.label;
  const lastRecap = bundle?.recaps?.[0]?.dm?.recap;

  return (
    <div className="player-table">
      <LiveUpdates
        sessionSlug={sessionSlug}
        onTranscriptUpdate={setLiveLines}
        onChangelogUpdate={setLiveChangelog}
        onRollUpdate={setLiveRolls}
      />
      <style>{tableCSS}</style>
      <header className="session-header">
        <div className="session-core">
          <div className="session-title">
            <h2>{characterName}</h2>
            <span className="class-pill">{characterClass}</span>
          </div>
          <div className="session-meta">
            <span>{location}</span>
            <span>HP {hpLabel}</span>
            <span>AC {acValue}</span>
          </div>
          {(stakesLine1 || stakesLine2) && (
            <div className="session-stakes">
              {stakesLine1 && <div>{stakesLine1}</div>}
              {stakesLine2 && <div>{stakesLine2}</div>}
            </div>
          )}
        </div>
        <div className="header-actions">
          <button className="ghost" onClick={onBack}>Leave table</button>
          <button className="linkish" onClick={onAdvanced}>Settings</button>
        </div>
      </header>

      <main className="table-layout">
        <section className="chat">
          <div className="chat-feed">
            {chat.length === 0 && <div className="panel">No turns yet. Tell the DM what you do.</div>}
            {chat.map((msg, idx) => (
              <div key={idx} className={`chat-line ${msg.role}`}>
                <div className="chat-label">
                  {msg.role === 'dm' ? 'DM' : msg.role === 'roll' ? 'Roll' : msg.role === 'log' ? 'Log' : 'You'}
                </div>
                <div className="chat-text">{msg.text}</div>
                {msg.recap && <div className="chat-recap">{msg.recap}</div>}
                {msg.stakes && <div className="chat-stakes">Stakes: {msg.stakes}</div>}
              </div>
            ))}
          </div>
          {rollRequest && (
            <div className="roll-panel">
              <div>
                <div className="roll-title">{formatRollRequest(rollRequest)}</div>
                {rollRequest.reason && <div className="subtle">{rollRequest.reason}</div>}
              </div>
              <div className="roll-actions">
                <button className="primary" onClick={handleRollAndSend}>Roll &amp; Send</button>
                <button className="ghost" onClick={handleRoll}>Roll</button>
                {typeof rollRequest.dc === 'number' && <div className="dc-pill">DC {rollRequest.dc}</div>}
              </div>
              {rollResult && (
                <div className="roll-result">
                  {formatRollResult(rollResult)}
                </div>
              )}
            </div>
          )}
          <div className="composer">
            <label>What do you do?</label>
            {rollRequest && <div className="subtle">The DM is waiting for a roll.</div>}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={inputPlaceholder}
              rows={3}
            />
            <div className="composer-actions">
              <div className="suggestions">
                <div className="suggestions-label">Suggestions</div>
                <div className="suggestions-note">You can do anything. These are just ideas.</div>
                <div className="suggestion-chips">
                  {displaySuggestions.slice(0, 5).map((suggestion) => (
                    <button key={suggestion} onClick={() => setInput(suggestion)}>{suggestion}</button>
                  ))}
                </div>
              </div>
              <button className="primary" onClick={() => sendAction()} disabled={sending}>{sending ? 'Sending...' : 'Send'}</button>
            </div>
            {error && (
              <div className="error">
                <div>{error}</div>
                {retryAction && (
                  <button className="ghost" onClick={() => sendAction(retryAction)}>Retry</button>
                )}
              </div>
            )}
            {isFetching && <div className="subtle">Refreshing table...</div>}
          </div>
        </section>

        <aside className="sidebar">
          <div className="card">
            <div className="card-header">
              <div>
                <h3>Character Sheet</h3>
                <p className="subtle">{bundle?.character?.race || bundle?.character?.ancestry || 'Unknown'}</p>
              </div>
              <button className="toggle" onClick={() => setIsCharacterOpen((prev) => !prev)}>
                {isCharacterOpen ? 'Hide' : 'Show'}
              </button>
            </div>
            {isCharacterOpen && (
              <div className="card-body">
                <div className="stat-row">
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
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Journal</h3>
              <button className="toggle" onClick={() => setIsJournalOpen((prev) => !prev)}>
                {isJournalOpen ? 'Hide' : 'Show'}
              </button>
            </div>
            {isJournalOpen && (
              <div className="card-body">
                {hookLabel && (
                  <div className="section">
                    <h4>Hook</h4>
                    <p>{hookLabel}</p>
                  </div>
                )}
                {activeQuests.length > 0 && (
                  <div className="section">
                    <h4>Active quests</h4>
                    <ul>
                      {activeQuests.map((quest: any) => (
                        <li key={quest.id || quest.name || quest.title}>
                          <strong>{quest.title || quest.name || quest.id}</strong>
                          {quest.status && <span className="subtle"> - {quest.status}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {bundle?.discoveries && bundle.discoveries.length > 0 && (
                  <div className="section">
                    <h4>Discoveries & Rumors</h4>
                    <ul>
                      {bundle.discoveries.map((disc) => (
                        <li key={disc.name + disc.discovery_type}>
                          <strong>{disc.name || disc.discovery_type}</strong>
                          {disc.description && <div className="subtle">{disc.description}</div>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {keyNpcs.length > 0 && (
                  <div className="section">
                    <h4>Key NPCs</h4>
                    <ul>
                      {keyNpcs.map((npc: any, index: number) => {
                        if (typeof npc === 'string') {
                          return <li key={npc + index}>{npc}</li>;
                        }
                        const label = npc?.name || npc?.title || npc?.id || npc?.npc_id;
                        if (!label) return null;
                        return <li key={label + index}>{label}</li>;
                      })}
                    </ul>
                  </div>
                )}
                {lastRecap && (
                  <div className="section">
                    <h4>Last recap</h4>
                    <p>{lastRecap}</p>
                  </div>
                )}
              </div>
            )}
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
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.session-core { display: flex; flex-direction: column; gap: 6px; }
.session-title { display: flex; align-items: center; gap: 10px; }
.session-title h2 { margin: 0; font-size: 24px; }
.class-pill {
  background: #fffaf3;
  border: 1px solid #d9c3a3;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.session-meta { display: flex; gap: 14px; font-size: 13px; color: #6d5138; flex-wrap: wrap; }
.session-stakes { font-size: 13px; color: #4a2f1b; display: grid; gap: 4px; }
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
.chat-line.dm { border-color: #c19a6b; background: #fff7ea; }
.chat-line.player { align-self: flex-end; background: #fff; border-color: #e1c9a2; }
.chat-line.roll { background: #f1efe9; border-style: dashed; }
.chat-label { font-weight: 700; color: #8c5a2b; text-transform: uppercase; font-size: 12px; letter-spacing: 0.08em; }
.chat-text { margin: 6px 0 2px; white-space: pre-wrap; }
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
.suggestions-note { font-size: 12px; color: #6d5138; margin-bottom: 8px; }
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
.card-header { display: flex; align-items: center; gap: 10px; justify-content: space-between; }
.card-body { margin-top: 10px; }
.stat { background: #fffaf3; border: 1px solid #ecd7b6; border-radius: 10px; padding: 6px 10px; }
.stat .label { font-size: 12px; color: #6d5138; }
.stat .value { font-weight: 800; color: #2d1b0b; }
.stat-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.toggle {
  border-radius: 999px;
  padding: 6px 12px;
  border: 1px solid #d9c3a3;
  background: #fffaf3;
  color: #6d5138;
  font-weight: 700;
  cursor: pointer;
}
@media (max-width: 1000px) {
  .table-layout { grid-template-columns: 1fr; }
  .chat-feed { max-height: none; }
  .session-header { flex-direction: column; align-items: flex-start; }
}
`;

export default PlayerTable;




