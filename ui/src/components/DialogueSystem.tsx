import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

interface NPCDialogue {
  id: string;
  name: string;
  portrait: string;
  currentDialogue: string;
  dialogueOptions: string[];
  mood: string;
  relationship: string;
}

interface DialogueSystemProps {
  sessionSlug: string;
  npcId: string;
  onClose: () => void;
  onDialogueEnd: () => void;
}

const DialogueSystem: React.FC<DialogueSystemProps> = ({ sessionSlug, npcId, onClose, onDialogueEnd }) => {
  const [dialogueHistory, setDialogueHistory] = useState<{sender: string; message: string}[]>([]);
  const [currentDialogue, setCurrentDialogue] = useState<NPCDialogue | null>(null);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [typingMessage, setTypingMessage] = useState('');
  const [npcTyping, setNpcTyping] = useState(false);

  // Mock NPC data - in a real implementation, this would come from the API
  const { data: npcData, isLoading: isNpcLoading } = useQuery({
    queryKey: ['npc-dialogue', sessionSlug, npcId],
    queryFn: async () => {
      // Mock data - replace with actual API call
      const mockNPCs = {
        'guard-001': {
          id: 'guard-001',
          name: 'Captain Aldric',
          portrait: '👮',
          currentDialogue: 'Greetings, traveler! What brings you to our fair town?',
          dialogueOptions: [
            'I seek adventure!',
            'Just passing through.',
            'Do you have any quests?',
            'Tell me about this town.'
          ],
          mood: 'friendly',
          relationship: 'neutral'
        },
        'merchant-001': {
          id: 'merchant-001',
          name: 'Eldrin the Merchant',
          portrait: '👨💼',
          currentDialogue: 'Ah, welcome to my humble shop! How may I serve you today?',
          dialogueOptions: [
            'What do you have for sale?',
            'I need supplies for my journey.',
            'Any rare items available?',
            'Just browsing, thanks.'
          ],
          mood: 'helpful',
          relationship: 'neutral'
        }
      };
      
      return mockNPCs[npcId as keyof typeof mockNPCs] || null;
    },
  });

  const { data: character } = useQuery({
    queryKey: ['character', sessionSlug],
    queryFn: () => fetch(`/api/data/characters/${sessionSlug}.json`).then(r => r.json()),
  });

  useEffect(() => {
    if (npcData) {
      setCurrentDialogue(npcData);
      // Add initial NPC message to history
      setDialogueHistory([
        { sender: npcData.name, message: npcData.currentDialogue }
      ]);
    }
  }, [npcData]);

  const handleOptionSelect = (optionIndex: number) => {
    if (!currentDialogue) return;
    
    setSelectedOption(optionIndex);
    const selectedMessage = currentDialogue.dialogueOptions[optionIndex];
    
    // Add player message to history
    setDialogueHistory(prev => [
      ...prev,
      { sender: character?.name || 'You', message: selectedMessage }
    ]);
    
    // Simulate NPC typing
    setNpcTyping(true);
    
    // Generate NPC response based on selected option
    setTimeout(() => {
      const responses = [
        'Excellent! I have just the quest for an adventurer like you...',
        'Safe travels then, friend. The roads can be dangerous.',
        'As a matter of fact, we do need help with a local problem...',
        'Briarwood is a peaceful town, but we have our share of troubles.'
      ];
      
      const npcResponse = responses[optionIndex] || 'Interesting... tell me more.';
      
      setDialogueHistory(prev => [
        ...prev,
        { sender: currentDialogue.name, message: npcResponse }
      ]);
      
      setNpcTyping(false);
      
      // Update dialogue options for next round
      const newOptions = [
        'Tell me about this quest!',
        'What kind of dangers?',
        'I accept the quest!',
        'What troubles do you face?'
      ];
      
      setCurrentDialogue(prev => prev ? {
        ...prev,
        currentDialogue: npcResponse,
        dialogueOptions: newOptions
      } : null);
    }, 1500);
  };

  const handleSendMessage = () => {
    if (typingMessage.trim() && currentDialogue) {
      // Add player message to history
      setDialogueHistory(prev => [
        ...prev,
        { sender: character?.name || 'You', message: typingMessage }
      ]);
      
      setTypingMessage('');
      setNpcTyping(true);
      
      // Simulate NPC response
      setTimeout(() => {
        const npcResponse = `Interesting, ${character?.name || 'adventurer'}. I'll consider what you've said.`;
        
        setDialogueHistory(prev => [
          ...prev,
          { sender: currentDialogue.name, message: npcResponse }
        ]);
        
        setNpcTyping(false);
        
        setCurrentDialogue(prev => prev ? {
          ...prev,
          currentDialogue: npcResponse
        } : null);
      }, 1500);
    }
  };

  const getMoodColor = (mood: string) => {
    switch (mood) {
      case 'friendly': return '#81C784';
      case 'helpful': return '#4FC3F7';
      case 'hostile': return '#E57373';
      case 'suspicious': return '#FFB74D';
      case 'neutral': return '#9E9E9E';
      default: return '#9E9E9E';
    }
  };

  const getRelationshipColor = (relationship: string) => {
    switch (relationship) {
      case 'ally': return '#81C784';
      case 'friend': return '#64B5F6';
      case 'neutral': return '#FFD54F';
      case 'enemy': return '#E57373';
      default: return '#BDBDBD';
    }
  };

  if (isNpcLoading) return (
    <div className="dialogue-system">
      <div className="loading-overlay">
        <div className="loading-spinner"></div>
        <p>Preparing dialogue...</p>
      </div>
    </div>
  );

  if (!currentDialogue) return (
    <div className="dialogue-system">
      <div className="error-message">NPC not found</div>
    </div>
  );

  return (
    <div className="dialogue-system">
      <style>{dialogueCSS}</style>

      <div className="dialogue-header">
        <div className="npc-info">
          <div className="npc-portrait">
            {currentDialogue.portrait}
          </div>
          <div className="npc-details">
            <h3>{currentDialogue.name}</h3>
            <div className="npc-status">
              <span 
                className="mood-indicator"
                style={{ backgroundColor: getMoodColor(currentDialogue.mood) }}
              >
                {currentDialogue.mood}
              </span>
              <span 
                className="relationship-indicator"
                style={{ backgroundColor: getRelationshipColor(currentDialogue.relationship) }}
              >
                {currentDialogue.relationship}
              </span>
            </div>
          </div>
        </div>
        <button onClick={onClose} className="close-button">×</button>
      </div>

      <div className="dialogue-content">
        <div className="dialogue-history">
          {dialogueHistory.map((entry, index) => (
            <div key={index} className={`dialogue-entry ${entry.sender === currentDialogue.name ? 'npc' : 'player'}`}>
              <div className="dialogue-sender">{entry.sender}</div>
              <div className="dialogue-message">{entry.message}</div>
            </div>
          ))}
          
          {npcTyping && (
            <div className="dialogue-entry npc typing">
              <div className="dialogue-sender">{currentDialogue.name}</div>
              <div className="dialogue-message">
                <span className="typing-indicator">●●●</span>
              </div>
            </div>
          )}
        </div>

        {currentDialogue.dialogueOptions.length > 0 ? (
          <div className="dialogue-options">
            <h4>What will you say?</h4>
            <div className="options-grid">
              {currentDialogue.dialogueOptions.map((option, index) => (
                <button
                  key={index}
                  onClick={() => handleOptionSelect(index)}
                  className={`option-button ${selectedOption === index ? 'selected' : ''}`}
                  disabled={npcTyping}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="dialogue-input">
            <textarea
              value={typingMessage}
              onChange={(e) => setTypingMessage(e.target.value)}
              placeholder="Type your response..."
              disabled={npcTyping}
              rows={3}
            />
            <button
              onClick={handleSendMessage}
              disabled={!typingMessage.trim() || npcTyping}
              className="send-button"
            >
              Send
            </button>
          </div>
        )}
      </div>

      <div className="dialogue-footer">
        <button onClick={onDialogueEnd} className="end-dialogue-button">
          End Conversation
        </button>
      </div>
    </div>
  );
};

// CSS for the dialogue system
const dialogueCSS = `
.dialogue-system {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 600px;
  max-width: 90vw;
  background-color: #f8f4e8;
  border: 3px solid #8B4513;
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  z-index: 1002;
  font-family: 'Georgia', serif;
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}

.dialogue-header {
  background-color: #8B4513;
  color: white;
  padding: 15px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 10px 10px 0 0;
}

.npc-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.npc-portrait {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background-color: gold;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  border: 2px solid #D4AF37;
}

.npc-details h3 {
  margin: 0;
  font-size: 18px;
}

.npc-status {
  display: flex;
  gap: 8px;
  margin-top: 5px;
}

.mood-indicator, .relationship-indicator {
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 10px;
  color: white;
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

.dialogue-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.dialogue-history {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 15px;
  padding-right: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dialogue-entry {
  padding: 10px 15px;
  border-radius: 8px;
  max-width: 80%;
  word-wrap: break-word;
}

.dialogue-entry.npc {
  align-self: flex-start;
  background-color: #e8f4f8;
  border-bottom-left-radius: 0;
}

.dialogue-entry.player {
  align-self: flex-end;
  background-color: #fff3cd;
  border-bottom-right-radius: 0;
}

.dialogue-entry.typing {
  background-color: #f0f0f0;
}

.dialogue-sender {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 3px;
  color: #8B4513;
}

.dialogue-message {
  font-size: 14px;
  line-height: 1.4;
}

.typing-indicator {
  display: inline-block;
  width: 20px;
  animation: typing 1s steps(3, end) infinite;
}

@keyframes typing {
  0% { content: '●'; }
  33% { content: '●●'; }
  66% { content: '●●●'; }
  100% { content: '●'; }
}

.dialogue-options {
  margin-top: auto;
}

.dialogue-options h4 {
  margin: 0 0 10px 0;
  color: #8B4513;
}

.options-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.option-button {
  padding: 10px;
  background-color: white;
  border: 1px solid #8B4513;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.option-button:hover {
  background-color: #f0e6d2;
}

.option-button.selected {
  background-color: #8B4513;
  color: white;
}

.option-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.dialogue-input {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: auto;
}

.dialogue-input textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  resize: none;
  font-family: inherit;
}

.send-button {
  align-self: flex-end;
  padding: 8px 15px;
  background-color: #8B4513;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.send-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.dialogue-footer {
  background-color: #f0f0f0;
  padding: 10px 20px;
  border-radius: 0 0 10px 10px;
  text-align: right;
}

.end-dialogue-button {
  padding: 8px 15px;
  background-color: #e57373;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.end-dialogue-button:hover {
  background-color: #ef5350;
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

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-message {
  padding: 20px;
  text-align: center;
  color: #e57373;
}
`;

export default DialogueSystem;
