import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

interface JournalEntry {
  id: string;
  timestamp: string;
  type: string;
  content: string;
  location?: string;
  mood?: string;
}

interface AdventureJournalProps {
  sessionSlug: string;
  onAddEntry?: (content: string) => void;
}

const fetchJournalEntries = async (sessionSlug: string): Promise<JournalEntry[]> => {
  // For now, we'll use the transcript as journal entries
  // In a future enhancement, we could have a dedicated journal endpoint
  const response = await fetch(`/api/sessions/${sessionSlug}/transcript`);
  if (!response.ok) throw new Error('Failed to fetch journal entries');
  
  const data = await response.json();
  return data.items.map((item, index) => ({
    id: `entry-${index}`,
    timestamp: item.timestamp || new Date().toISOString(),
    type: item.type || 'general',
    content: item.text || item,
    location: item.location,
    mood: item.mood || 'neutral'
  }));
};

const AdventureJournal: React.FC<AdventureJournalProps> = ({ sessionSlug, onAddEntry }) => {
  const [newEntryContent, setNewEntryContent] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);

  const { data: entries, isLoading, error, refetch } = useQuery({
    queryKey: ['journal', sessionSlug],
    queryFn: () => fetchJournalEntries(sessionSlug),
  });

  const filteredEntries = entries?.filter(entry => {
    // Filter by type
    if (filterType !== 'all' && entry.type !== filterType) return false;
    
    // Filter by search term
    if (searchTerm && !entry.content.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    
    return true;
  }) || [];

  const handleAddEntry = () => {
    if (newEntryContent.trim() && onAddEntry) {
      onAddEntry(newEntryContent);
      setNewEntryContent('');
      refetch();
    }
  };

  const getEntryIcon = (type: string) => {
    switch (type) {
      case 'combat': return '⚔️';
      case 'discovery': return '🔍';
      case 'dialogue': return '💬';
      case 'quest': return '📜';
      case 'rest': return '🛌️';
      case 'travel': return '🗺️';
      default: return '📝';
    }
  };

  const getMoodColor = (mood: string) => {
    switch (mood) {
      case 'dangerous': return '#ff6b6b';
      case 'exciting': return '#ffa502';
      case 'mysterious': return '#800080';
      case 'peaceful': return '#51cf66';
      case 'sad': return '#74b9ff';
      default: return '#2d3436';
    }
  };

  if (isLoading) return (
    <div className="adventure-journal">
      <div className="journal-header">
        <h3>Adventure Journal</h3>
        <div className="loading-spinner">Loading...</div>
      </div>
    </div>
  );

  if (error) return (
    <div className="adventure-journal">
      <div className="journal-header">
        <h3>Adventure Journal</h3>
        <div className="error-message">Failed to load journal entries</div>
      </div>
    </div>
  );

  return (
    <div className="adventure-journal">
      <div className="journal-header">
        <h3>📖 Adventure Journal</h3>
        <div className="journal-controls">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Entries</option>
            <option value="combat">Combat</option>
            <option value="discovery">Discoveries</option>
            <option value="dialogue">Dialogues</option>
            <option value="quest">Quests</option>
            <option value="rest">Rests</option>
            <option value="travel">Travel</option>
          </select>
          
          <input
            type="text"
            placeholder="Search entries..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
      </div>

      <div className="journal-entries">
        {filteredEntries.length === 0 ? (
          <div className="no-entries">
            <p>No journal entries found. Your adventure awaits!</p>
            <p>Start exploring to fill your journal with tales of heroism.</p>
          </div>
        ) : (
          filteredEntries.map((entry) => (
            <div key={entry.id} className="journal-entry">
              <div className="entry-header">
                <div className="entry-icon" style={{ backgroundColor: getMoodColor(entry.mood || 'neutral') }}>
                  {getEntryIcon(entry.type)}
                </div>
                <div className="entry-meta">
                  <span className="entry-time">
                    {new Date(entry.timestamp).toLocaleString()}
                  </span>
                  {entry.location && (
                    <span className="entry-location">• {entry.location}</span>
                  )}
                </div>
              </div>
              
              <div className="entry-content">
                <div className={`entry-text ${expandedEntry === entry.id ? 'expanded' : ''}`}>
                  {entry.content}
                </div>
                {entry.content.length > 200 && (
                  <button
                    className="read-more"
                    onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
                  >
                    {expandedEntry === entry.id ? 'Read Less' : 'Read More'}
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="journal-footer">
        <div className="new-entry-form">
          <textarea
            value={newEntryContent}
            onChange={(e) => setNewEntryContent(e.target.value)}
            placeholder="Add a personal note to your journal..."
            rows={3}
          />
          <button
            onClick={handleAddEntry}
            disabled={!newEntryContent.trim()}
            className="add-entry-button"
          >
            Add Note
          </button>
        </div>
        
        <div className="journal-stats">
          <span>📊 {filteredEntries.length} entries</span>
          <span>🗓️ {entries?.length || 0} total</span>
          <button onClick={refetch} className="refresh-button">↻ Refresh</button>
        </div>
      </div>
    </div>
  );
};

// Add some basic CSS for the journal
export const adventureJournalCSS = `
.adventure-journal {
  border: 2px solid #8B4513;
  border-radius: 8px;
  margin: 15px;
  padding: 15px;
  background-color: #f5e7d3;
  font-family: 'Georgia', serif;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.journal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #8B4513;
}

.journal-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.filter-select, .search-input {
  padding: 5px 10px;
  border: 1px solid #8B4513;
  border-radius: 4px;
  background-color: white;
}

.journal-entries {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 15px;
  padding-right: 5px;
}

.journal-entry {
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.entry-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 10px;
}

.entry-icon {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 16px;
}

.entry-meta {
  font-size: 12px;
  color: #666;
  display: flex;
  gap: 10px;
}

.entry-content {
  color: #333;
  line-height: 1.4;
}

.entry-text.expanded {
  white-space: pre-wrap;
}

.read-more {
  background: none;
  border: none;
  color: #8B4513;
  cursor: pointer;
  font-size: 12px;
  margin-top: 5px;
}

.no-entries {
  text-align: center;
  padding: 20px;
  color: #666;
  font-style: italic;
}

.journal-footer {
  border-top: 1px solid #8B4513;
  padding-top: 10px;
  margin-top: 10px;
}

.new-entry-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.new-entry-form textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #8B4513;
  border-radius: 4px;
  resize: vertical;
  font-family: inherit;
}

.add-entry-button {
  align-self: flex-end;
  padding: 6px 12px;
  background-color: #8B4513;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.add-entry-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.journal-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #666;
}

.refresh-button {
  background: none;
  border: none;
  cursor: pointer;
  color: #8B4513;
}
`;

export default AdventureJournal;