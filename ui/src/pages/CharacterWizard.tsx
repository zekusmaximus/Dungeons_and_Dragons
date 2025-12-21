import React, { useMemo, useState } from 'react';

interface CharacterWizardProps {
  sessionSlug: string;
  onComplete: (slug: string) => void;
  onBack: () => void;
}

type AbilityKey = 'str' | 'dex' | 'con' | 'int' | 'wis' | 'cha';

const abilityKeys: AbilityKey[] = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
const standardArray = [15, 14, 13, 12, 10, 8];

const equipmentPacks = [
  {
    id: 'A',
    label: 'Lightfoot',
    description: 'Quiet, quick, good for slipping past danger.',
    items: ['Leather armor', 'Shortsword', 'Shortbow (20 arrows)', "Explorer's pack"],
    armor: { base: 11, maxDex: null, shield: false },
    gp: 15,
  },
  {
    id: 'B',
    label: 'Frontliner',
    description: 'Shield and steel for leading the way.',
    items: ['Chain mail', 'Shield', 'Longsword', "Dungeoneer's pack"],
    armor: { base: 16, maxDex: 0, shield: true },
    gp: 10,
  },
];

const skillOptions = ['athletics', 'perception', 'survival', 'stealth', 'investigation', 'persuasion'];
const hookOptions = ['Classic dungeon', 'Urban mystery', 'Wilderness survival', 'Political intrigue', 'Horror'];

const abilityCost = (score: number) => {
  if (score <= 8) return 0;
  if (score === 9) return 1;
  if (score === 10) return 2;
  if (score === 11) return 3;
  if (score === 12) return 4;
  if (score === 13) return 5;
  if (score === 14) return 7;
  if (score === 15) return 9;
  return 10;
};

const rollStat = () => {
  const rolls = Array.from({ length: 4 }, () => 1 + Math.floor(Math.random() * 6));
  const sorted = rolls.sort((a, b) => b - a);
  return sorted[0] + sorted[1] + sorted[2];
};

const CharacterWizard: React.FC<CharacterWizardProps> = ({ sessionSlug, onComplete, onBack }) => {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [ancestry, setAncestry] = useState('Human');
  const [klass, setKlass] = useState('Fighter');
  const [background, setBackground] = useState('Wanderer');
  const [level, setLevel] = useState(1);
  const [abilityMethod, setAbilityMethod] = useState<'standard' | 'roll' | 'point-buy'>('standard');
  const [abilities, setAbilities] = useState<Record<AbilityKey, number>>({
    str: 15,
    dex: 14,
    con: 13,
    int: 12,
    wis: 10,
    cha: 8,
  });
  const [selectedSkills, setSelectedSkills] = useState<string[]>(['perception']);
  const [languages, setLanguages] = useState<string>('Common');
  const [notes, setNotes] = useState('');
  const [selectedPack, setSelectedPack] = useState(equipmentPacks[0]);
  const [selectedHook, setSelectedHook] = useState(hookOptions[0]);
  const [spells, setSpells] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pointBuySpent = useMemo(
    () => abilityKeys.reduce((sum, key) => sum + abilityCost(abilities[key]), 0),
    [abilities],
  );
  const pointBuyRemaining = 27 - pointBuySpent;

  const abilityModifier = (score: number) => Math.floor((score - 10) / 2);
  const hitDie = useMemo(() => {
    const name = klass.trim().toLowerCase();
    if (name === 'barbarian') return 12;
    if (['fighter', 'paladin', 'ranger'].includes(name)) return 10;
    if (['rogue', 'bard', 'cleric', 'druid', 'monk', 'warlock'].includes(name)) return 8;
    if (['wizard', 'sorcerer'].includes(name)) return 6;
    return 8;
  }, [klass]);
  const derivedHp = useMemo(() => {
    const conMod = abilityModifier(abilities.con);
    if (level <= 1) return Math.max(1, hitDie + conMod);
    const avgPerLevel = Math.floor(hitDie / 2) + 1;
    return Math.max(1, hitDie + conMod + (level - 1) * (avgPerLevel + conMod));
  }, [abilities.con, hitDie, level]);
  const derivedAc = useMemo(() => {
    const dexMod = abilityModifier(abilities.dex);
    const base = selectedPack.armor?.base ?? 10;
    const maxDex = selectedPack.armor?.maxDex;
    const dexBonus = maxDex === null || maxDex === undefined ? dexMod : Math.min(dexMod, maxDex);
    const shieldBonus = selectedPack.armor?.shield ? 2 : 0;
    return Math.max(1, base + dexBonus + shieldBonus);
  }, [abilities.dex, selectedPack]);
  const computePackAc = (pack: (typeof equipmentPacks)[number]) => {
    const dexMod = abilityModifier(abilities.dex);
    const base = pack.armor?.base ?? 10;
    const maxDex = pack.armor?.maxDex;
    const dexBonus = maxDex === null || maxDex === undefined ? dexMod : Math.min(dexMod, maxDex);
    const shieldBonus = pack.armor?.shield ? 2 : 0;
    return Math.max(1, base + dexBonus + shieldBonus);
  };

  const setMethod = (method: 'standard' | 'roll' | 'point-buy') => {
    setAbilityMethod(method);
    if (method === 'standard') {
      const mapped: Record<AbilityKey, number> = { str: 15, dex: 14, con: 13, int: 12, wis: 10, cha: 8 };
      setAbilities(mapped);
    } else if (method === 'point-buy') {
      const mapped: Record<AbilityKey, number> = { str: 8, dex: 8, con: 8, int: 8, wis: 8, cha: 8 };
      setAbilities(mapped);
    } else {
      const rolled = abilityKeys.reduce((acc, key, idx) => {
        acc[key] = standardArray[idx];
        return acc;
      }, {} as Record<AbilityKey, number>);
      setAbilities(rolled);
    }
  };

  const applyRoll = () => {
    const rolled = abilityKeys.reduce((acc, key) => {
      acc[key] = rollStat();
      return acc;
    }, {} as Record<AbilityKey, number>);
    setAbilities(rolled);
    setAbilityMethod('roll');
  };

  const adjustAbility = (key: AbilityKey, delta: number) => {
    const next = { ...abilities };
    const newScore = (next[key] || 8) + delta;
    if (newScore < 8 || newScore > 18) return;
    if (abilityMethod === 'point-buy') {
      const currentCost = abilityCost(next[key]);
      const nextCost = abilityCost(newScore);
      const tentativeRemaining = pointBuyRemaining + currentCost - nextCost;
      if (tentativeRemaining < 0) return;
      next[key] = newScore;
      setAbilities(next);
      return;
    }
    next[key] = newScore;
    setAbilities(next);
  };

  const toggleSkill = (skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill].slice(0, 4),
    );
  };

  const canAdvanceStep = () => {
    if (step === 1) return !!name.trim();
    if (step === 2 && abilityMethod === 'point-buy') return pointBuyRemaining >= 0;
    return true;
  };

  const submitCharacter = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        name,
        ancestry,
        class: klass,
        background,
        level,
        hp: derivedHp,
        ac: derivedAc,
        gp: selectedPack.gp,
        abilities,
        skills: selectedSkills,
        proficiencies: selectedSkills,
        tools: [],
        languages: languages.split(',').map((l) => l.trim()).filter(Boolean),
        equipment: selectedPack.items,
        spells: spells
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
        notes,
        starting_location: 'Camp',
        method: abilityMethod,
        hook: selectedHook,
      };
      const response = await fetch(`/api/sessions/${sessionSlug}/character`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Could not create character');
      }
      await fetch(`/api/sessions/${sessionSlug}/player/opening`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hook: selectedHook }),
      });
      onComplete(sessionSlug);
    } catch (e: any) {
      setError(e.message || 'Unable to save character');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="wizard">
      <style>{wizardCSS}</style>
      <div className="wizard__header">
        <div>
          <p className="eyebrow">Character Wizard</p>
          <h2>Create your hero</h2>
        </div>
        <div className="wizard__actions">
          <button className="ghost" onClick={onBack}>Back</button>
          <button className="primary" onClick={submitCharacter} disabled={!canAdvanceStep() || submitting || step !== 5}>
            {submitting ? 'Creating...' : 'Review & Create'}
          </button>
        </div>
      </div>

      <div className="wizard__steps">
        {[1, 2, 3, 4, 5].map((s) => (
          <div key={s} className={`step ${s === step ? 'active' : s < step ? 'done' : ''}`}>
            <span>{s}</span>
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="panel grid-two">
          <div>
            <label>Hero name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Sable Ardent" />
            <label>Ancestry</label>
            <input value={ancestry} onChange={(e) => setAncestry(e.target.value)} />
            <label>Class</label>
            <input value={klass} onChange={(e) => setKlass(e.target.value)} />
            <label>Background</label>
            <input value={background} onChange={(e) => setBackground(e.target.value)} />
          </div>
          <div>
            <label>Level</label>
            <input type="number" min={1} value={level} onChange={(e) => setLevel(Number(e.target.value) || 1)} />
            <label>Languages</label>
            <input value={languages} onChange={(e) => setLanguages(e.target.value)} />
            <label>Notes</label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={5} />
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="panel">
          <div className="method-row">
            <label>Ability generation</label>
            <div className="method-buttons">
              <button className={abilityMethod === 'standard' ? 'pill active' : 'pill'} onClick={() => setMethod('standard')}>
                Standard array
              </button>
              <button className={abilityMethod === 'roll' ? 'pill active' : 'pill'} onClick={applyRoll}>
                Roll 4d6 drop lowest
              </button>
              <button className={abilityMethod === 'point-buy' ? 'pill active' : 'pill'} onClick={() => setMethod('point-buy')}>
                Point buy
              </button>
            </div>
            {abilityMethod === 'point-buy' && (
              <div className={`point-pool ${pointBuyRemaining < 0 ? 'error' : ''}`}>
                {pointBuyRemaining} points remaining
              </div>
            )}
          </div>

          <div className="abilities">
            {abilityKeys.map((key) => (
              <div key={key} className="ability-card">
                <div className="ability-name">{key.toUpperCase()}</div>
                <div className="ability-score">{abilities[key]}</div>
                <div className="ability-mod">Mod {abilityModifier(abilities[key]) >= 0 ? '+' : ''}{abilityModifier(abilities[key])}</div>
                <div className="ability-controls">
                  <button onClick={() => adjustAbility(key, -1)}>-</button>
                  <button onClick={() => adjustAbility(key, 1)}>+</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="panel">
          <div className="skills">
            {skillOptions.map((skill) => (
              <label key={skill} className={`skill ${selectedSkills.includes(skill) ? 'active' : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedSkills.includes(skill)}
                  onChange={() => toggleSkill(skill)}
                />
                {skill}
              </label>
            ))}
          </div>
          <p className="hint">Pick a few proficiencies that fit your class and background.</p>
        </div>
      )}

      {step === 4 && (
        <div className="panel grid-two">
          <div className="packs">
            {equipmentPacks.map((pack) => (
              <button
                key={pack.id}
                className={`pack ${selectedPack.id === pack.id ? 'active' : ''}`}
                onClick={() => setSelectedPack(pack)}
              >
                <div className="pack-title">{pack.label}</div>
                <div className="pack-body">{pack.description}</div>
                <div className="pack-items">{pack.items.join(', ')}</div>
                <div className="pack-stats">AC {computePackAc(pack)} / HP {derivedHp} / {pack.gp} gp</div>
              </button>
            ))}
          </div>
          <div>
            <label>Spells (optional, one per line)</label>
            <textarea value={spells} onChange={(e) => setSpells(e.target.value)} rows={8} placeholder="Guidance&#10;Cure Wounds" />
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="panel review">
          <div>
            <h3>{name || 'Unnamed hero'}</h3>
            <p>{ancestry} {klass} · {background}</p>
            <p>Level {level} / AC {derivedAc} / HP {derivedHp} / {selectedPack.gp} gp</p>
          </div>
          <div className="review-grid">
            <div>
              <h4>Abilities</h4>
              <ul>
                {abilityKeys.map((key) => (
                  <li key={key}>{key.toUpperCase()}: {abilities[key]} ({abilityModifier(abilities[key]) >= 0 ? '+' : ''}{abilityModifier(abilities[key])})</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Skills</h4>
              <p>{selectedSkills.join(', ') || 'None selected'}</p>
              <h4>Equipment</h4>
              <p>{selectedPack.items.join(', ')}</p>
            </div>
            <div>
              <h4>Notes</h4>
              <p>{notes || 'Ready to explore.'}</p>
            </div>
          </div>
          <div className="hook-picker">
            <h4>Adventure hook</h4>
            <div className="hook-options">
              {hookOptions.map((hook) => (
                <button
                  key={hook}
                  className={`hook-pill ${selectedHook === hook ? 'active' : ''}`}
                  onClick={() => setSelectedHook(hook)}
                >
                  {hook}
                </button>
              ))}
            </div>
          </div>
          {error && <div className="error">{error}</div>}
        </div>
      )}

      <div className="wizard__footer">
        <button className="ghost" onClick={onBack}>Cancel</button>
        <div className="footer-steps">
          {step > 1 && <button className="ghost" onClick={() => setStep(step - 1)}>Back</button>}
          {step < 5 && (
            <button className="primary" onClick={() => setStep(step + 1)} disabled={!canAdvanceStep()}>
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const wizardCSS = `
.wizard {
  background: #f7f1e3;
  min-height: 100vh;
  padding: 32px 36px 80px;
  color: #2d1b0b;
}
.wizard__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.wizard__actions { display: flex; gap: 10px; }
.wizard__steps {
  display: flex;
  gap: 6px;
  margin: 16px 0;
}
.step {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid #c19a6b;
  display: grid;
  place-items: center;
  color: #8c5a2b;
  background: #fffaf3;
}
.step.active { background: #c19a6b; color: #fff; }
.step.done { background: #8c5a2b; color: #fff; }
.panel {
  background: #fff;
  border: 1px solid #d9c3a3;
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.05);
}
.grid-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
label { font-weight: 600; display: block; margin: 8px 0 4px; }
input, textarea {
  width: 100%;
  border: 1px solid #c7b090;
  border-radius: 10px;
  padding: 10px;
  background: #fffaf3;
  font-size: 15px;
  color: #2d1b0b;
}
textarea { resize: vertical; }
.method-row { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.method-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
.pill {
  border-radius: 999px;
  border: 1px solid #c19a6b;
  padding: 8px 14px;
  background: #fff;
  cursor: pointer;
}
.pill.active { background: #c19a6b; color: #fff; }
.point-pool { font-weight: 700; color: #2d1b0b; }
.point-pool.error { color: #8c2b1e; }
.abilities {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
}
.ability-card {
  border: 1px solid #d9c3a3;
  border-radius: 10px;
  background: #fffaf3;
  padding: 10px;
  text-align: center;
}
.ability-name { font-weight: 700; color: #8c5a2b; }
.ability-score { font-size: 26px; margin: 4px 0; }
.ability-mod { color: #4a2f1b; margin-bottom: 6px; }
.ability-controls { display: flex; gap: 6px; justify-content: center; }
.ability-controls button {
  border-radius: 8px;
  border: 1px solid #c19a6b;
  background: #fff;
  padding: 4px 8px;
  cursor: pointer;
}
.skills { display: flex; flex-wrap: wrap; gap: 8px; }
.skill {
  border: 1px solid #d9c3a3;
  border-radius: 20px;
  padding: 8px 12px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
}
.skill.active { background: #c19a6b; color: #fff; border-color: #c19a6b; }
.packs { display: flex; flex-direction: column; gap: 10px; }
.pack {
  border: 1px solid #d9c3a3;
  border-radius: 12px;
  padding: 12px;
  background: #fffaf3;
  text-align: left;
  cursor: pointer;
}
.pack.active { border-color: #8c5a2b; box-shadow: 0 8px 18px rgba(0,0,0,0.06); }
.pack-title { font-weight: 700; color: #2d1b0b; }
.pack-body { color: #6d5138; margin: 6px 0; }
.pack-items { color: #4a2f1b; font-size: 14px; }
.pack-stats { color: #8c5a2b; font-weight: 700; margin-top: 6px; }
.review { display: flex; flex-direction: column; gap: 10px; }
.review-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.hook-picker { margin-top: 6px; }
.hook-options { display: flex; flex-wrap: wrap; gap: 8px; }
.hook-pill {
  border-radius: 999px;
  border: 1px solid #c19a6b;
  padding: 6px 12px;
  background: #fff;
  cursor: pointer;
}
.hook-pill.active { background: #8c5a2b; color: #fff; border-color: #8c5a2b; }
.wizard__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}
.primary, .ghost {
  border-radius: 10px;
  padding: 10px 16px;
  border: 1px solid #b9864c;
  font-weight: 700;
  cursor: pointer;
}
.primary { background: #b9864c; color: #fff; }
.ghost { background: transparent; color: #8c5a2b; }
.error {
  color: #8c2b1e;
  background: #ffe9e1;
  border: 1px solid #f5c1b5;
  padding: 8px 10px;
  border-radius: 8px;
}
@media (max-width: 900px) {
  .grid-two { grid-template-columns: 1fr; }
  .wizard { padding: 20px; }
}
`;

export default CharacterWizard;
