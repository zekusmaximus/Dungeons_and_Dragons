import React from 'react';
import { useQuery } from '@tanstack/react-query';

interface CharacterSheetProps {
  sessionSlug: string;
  onClose: () => void;
}

interface CharacterData {
  name: string;
  race: string;
  class: string;
  level: number;
  background: string;
  alignment: string;
  experience: number;
  abilities: {
    strength: number;
    dexterity: number;
    constitution: number;
    intelligence: number;
    wisdom: number;
    charisma: number;
  };
  skills: Record<string, boolean>;
  inventory: string[];
  equipment: {
    weapon?: string;
    armor?: string;
    shield?: string;
    accessories?: string[];
  };
  spells?: string[];
  features?: string[];
}

interface SessionState {
  hp: number;
  max_hp: number;
  ac: number;
  gold: number;
  conditions: string[];
  spell_slots?: Record<string, number>;
}

const CharacterSheet: React.FC<CharacterSheetProps> = ({ sessionSlug, onClose }) => {
  const { data: character, isLoading: isCharacterLoading } = useQuery({
    queryKey: ['character', sessionSlug],
    queryFn: () => fetch(`/api/data/characters/${sessionSlug}.json`).then(r => r.json()),
  });

  const { data: state, isLoading: isStateLoading } = useQuery({
    queryKey: ['state', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/state`).then(r => r.json()),
  });

  const isLoading = isCharacterLoading || isStateLoading;

  if (isLoading) return (
    <div className="character-sheet">
      <div className="loading-overlay">
        <div className="loading-spinner"></div>
        <p>Loading character sheet...</p>
      </div>
    </div>
  );

  if (!character) return (
    <div className="character-sheet">
      <div className="error-message">Character data not found</div>
    </div>
  );

  // Calculate ability modifiers
  const getModifier = (score: number) => Math.floor((score - 10) / 2);

  // Get proficiency bonus (assuming standard progression)
  const proficiencyBonus = Math.floor((character.level || 1) / 4) + 2;

  return (
    <div className="character-sheet">
      <style>{characterSheetCSS}</style>

      <div className="sheet-header">
        <h2>{character.name}</h2>
        <div className="basic-info">
          <span>{character.race} {character.class} Level {character.level}</span>
          <span>{character.background} • {character.alignment}</span>
        </div>
        <button onClick={onClose} className="close-button">×</button>
      </div>

      <div className="sheet-content">
        {/* Top Row: Stats and Combat Info */}
        <div className="top-row">
          <div className="combat-stats">
            <div className="stat-box">
              <div className="stat-label">HP</div>
              <div className="stat-value">
                {state?.hp || character.max_hp || '?'}/{state?.max_hp || character.max_hp || '?'}
              </div>
            </div>

            <div className="stat-box">
              <div className="stat-label">AC</div>
              <div className="stat-value">{state?.ac || character.ac || '?'}</div>
            </div>

            <div className="stat-box">
              <div className="stat-label">Initiative</div>
              <div className="stat-value">
                {getModifier(character.abilities?.dexterity || 10) >= 0 ? '+' : ''}
                {getModifier(character.abilities?.dexterity || 10)}
              </div>
            </div>

            <div className="stat-box">
              <div className="stat-label">Speed</div>
              <div className="stat-value">{character.speed || '30'} ft</div>
            </div>
          </div>

          <div className="character-portrait-large">
            <div className="portrait-placeholder-large">
              {character.class?.charAt(0).toUpperCase()}
            </div>
            <div className="xp-bar">
              <div
                className="xp-progress"
                style={{ width: `${Math.min(100, ((character.experience || 0) / 1000) * 100)}%` }}
              ></div>
              <span className="xp-text">XP: {character.experience || 0}/1000</span>
            </div>
          </div>
        </div>

        {/* Ability Scores */}
        <div className="ability-scores">
          <h3>Ability Scores</h3>
          <div className="abilities-grid">
            {Object.entries(character.abilities || {}).map(([ability, score]) => (
              <div key={ability} className="ability-box">
                <div className="ability-name">{ability.charAt(0).toUpperCase() + ability.slice(1).substring(0, 3)}</div>
                <div className="ability-score">{score}</div>
                <div className="ability-modifier">
                  {getModifier(score) >= 0 ? '+' : ''}{getModifier(score)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main Content Columns */}
        <div className="main-content">
          <div className="left-column">
            {/* Skills */}
            <div className="skills-section">
              <h3>Skills</h3>
              <div className="skills-grid">
                {Object.entries(character.skills || {}).map(([skill, isProficient]) => (
                  <div key={skill} className="skill-item">
                    <span className="skill-name">{skill}</span>
                    <span className="skill-bonus">
                      {isProficient ? '+' : ''}{getModifier(character.abilities?.intelligence || 10)}
                      {isProficient && ` + ${proficiencyBonus}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Inventory */}
            <div className="inventory-section">
              <h3>Inventory</h3>
              <div className="inventory-items">
                {character.inventory?.length ? (
                  <ul>
                    {character.inventory.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No items in inventory</p>
                )}
              </div>
              <div className="gold-display">
                💰 Gold: {state?.gold || 0} GP
              </div>
            </div>
          </div>

          <div className="right-column">
            {/* Equipment */}
            <div className="equipment-section">
              <h3>Equipment</h3>
              <div className="equipment-slots">
                <div className="equipment-slot">
                  <span className="slot-name">Weapon:</span>
                  <span className="slot-item">{character.equipment?.weapon || 'None'}</span>
                </div>
                <div className="equipment-slot">
                  <span className="slot-name">Armor:</span>
                  <span className="slot-item">{character.equipment?.armor || 'None'}</span>
                </div>
                <div className="equipment-slot">
                  <span className="slot-name">Shield:</span>
                  <span className="slot-item">{character.equipment?.shield || 'None'}</span>
                </div>
                {character.equipment?.accessories?.length && (
                  <div className="equipment-slot">
                    <span className="slot-name">Accessories:</span>
                    <span className="slot-item">{character.equipment.accessories.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Features and Traits */}
            <div className="features-section">
              <h3>Features & Traits</h3>
              <div className="features-list">
                {character.features?.length ? (
                  <ul>
                    {character.features.map((feature, index) => (
                      <li key={index}>{feature}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No special features</p>
                )}
              </div>
            </div>

            {/* Spells (if applicable) */}
            {character.spells?.length && (
              <div className="spells-section">
                <h3>Spells</h3>
                <div className="spells-list">
                  <ul>
                    {character.spells.map((spell, index) => (
                      <li key={index}>{spell}</li>
                    ))}
                  </ul>
                </div>
                {state?.spell_slots && (
                  <div className="spell-slots">
                    <h4>Spell Slots</h4>
                    <div className="slot-grid">
                      {Object.entries(state.spell_slots).map(([level, slots]) => (
                        <div key={level} className="slot-item">
                          <span>L{level}:</span>
                          <span>{slots}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Conditions */}
        {state?.conditions?.length && (
          <div className="conditions-section">
            <h3>Conditions</h3>
            <div className="conditions-list">
              {state.conditions.map((condition, index) => (
                <span key={index} className="condition-badge">{condition}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// CSS for the character sheet
const characterSheetCSS = `
.character-sheet {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 800px;
  max-width: 90vw;
  background-color: #f8f4e8;
  border: 3px solid #8B4513;
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  z-index: 1001;
  font-family: 'Georgia', serif;
  overflow: hidden;
}

.sheet-header {
  background-color: #8B4513;
  color: white;
  padding: 15px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
}

.sheet-header h2 {
  margin: 0;
  font-size: 24px;
}

.basic-info {
  display: flex;
  flex-direction: column;
  font-size: 14px;
  opacity: 0.9;
}

.close-button {
  background: none;
  border: none;
  color: white;
  font-size: 24px;
  cursor: pointer;
  padding: 5px;
}

.close-button:hover {
  opacity: 0.7;
}

.sheet-content {
  padding: 20px;
  max-height: 80vh;
  overflow-y: auto;
}

.top-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.combat-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.stat-box {
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
  color: #8B4513;
}

.character-portrait-large {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.portrait-placeholder-large {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background-color: gold;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  font-weight: bold;
  border: 3px solid #D4AF37;
  margin-bottom: 10px;
}

.xp-bar {
  width: 100%;
  height: 20px;
  background-color: #ddd;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
}

.xp-progress {
  height: 100%;
  background-color: #4CAF50;
  transition: width 0.3s ease;
}

.xp-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 10px;
  color: white;
  font-weight: bold;
}

.ability-scores {
  margin-bottom: 20px;
}

.ability-scores h3 {
  color: #8B4513;
  margin-bottom: 10px;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
}

.abilities-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}

.ability-box {
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
}

.ability-name {
  font-size: 10px;
  font-weight: bold;
  margin-bottom: 5px;
}

.ability-score {
  font-size: 20px;
  font-weight: bold;
  color: #8B4513;
}

.ability-modifier {
  font-size: 12px;
  color: #666;
  margin-top: 5px;
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.section-title {
  color: #8B4513;
  margin-bottom: 10px;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
}

.skills-section h3,
.inventory-section h3,
.equipment-section h3,
.features-section h3,
.spells-section h3 {
  color: #8B4513;
  margin-bottom: 10px;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
}

.skills-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.skill-item {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid #f0f0f0;
}

.skill-name {
  font-size: 14px;
}

.skill-bonus {
  font-size: 14px;
  font-weight: bold;
  color: #8B4513;
}

.inventory-items {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #eee;
  padding: 10px;
  background-color: white;
  margin-bottom: 10px;
}

.inventory-items ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.inventory-items li {
  padding: 5px 0;
  border-bottom: 1px solid #f0f0f0;
}

.gold-display {
  background-color: gold;
  color: #333;
  padding: 8px;
  border-radius: 4px;
  text-align: center;
  font-weight: bold;
}

.equipment-slots {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.equipment-slot {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}

.slot-name {
  font-weight: bold;
}

.slot-item {
  color: #666;
}

.features-list {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #eee;
  padding: 10px;
  background-color: white;
}

.features-list ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.features-list li {
  padding: 5px 0;
  border-bottom: 1px solid #f0f0f0;
}

.spells-list {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #eee;
  padding: 10px;
  background-color: white;
}

.spells-list ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.spells-list li {
  padding: 5px 0;
  border-bottom: 1px solid #f0f0f0;
}

.spell-slots h4 {
  margin: 10px 0 5px 0;
  color: #666;
}

.slot-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.slot-grid .slot-item {
  background-color: #8B4513;
  color: white;
  padding: 5px;
  border-radius: 4px;
  text-align: center;
  font-size: 12px;
}

.conditions-section {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.conditions-section h3 {
  color: #8B4513;
  margin-bottom: 10px;
}

.conditions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.condition-badge {
  background-color: #ff6b6b;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
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

.error-message {
  padding: 20px;
  text-align: center;
  color: #ff6b6b;
}
`;

export default CharacterSheet;