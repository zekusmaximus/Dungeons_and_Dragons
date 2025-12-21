import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

interface MapLocation {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  discovered: boolean;
  visited: boolean;
  description?: string;
}

interface ExplorationMapProps {
  sessionSlug: string;
  onLocationClick: (location: MapLocation) => void;
}

const ExplorationMap: React.FC<ExplorationMapProps> = ({ sessionSlug, onLocationClick }) => {
  const [mapSize] = useState({ width: 800, height: 600 });
  const [showGrid, setShowGrid] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState<MapLocation | null>(null);

  // Mock data - in a real implementation, this would come from the API
  const { data: locations, isLoading } = useQuery({
    queryKey: ['exploration-map', sessionSlug],
    queryFn: async () => {
      // This is mock data - replace with actual API call
      const mockLocations: MapLocation[] = [
        { id: 'town-001', name: 'Briarwood', type: 'town', x: 400, y: 300, discovered: true, visited: true, description: 'A bustling frontier town' },
        { id: 'dungeon-001', name: 'Blackfang Caverns', type: 'dungeon', x: 500, y: 200, discovered: true, visited: false, description: 'Rumored to be filled with goblins' },
        { id: 'forest-001', name: 'Whispering Woods', type: 'forest', x: 300, y: 250, discovered: true, visited: true, description: 'Ancient elven ruins hidden within' },
        { id: 'ruin-001', name: 'Forgotten Keep', type: 'ruin', x: 550, y: 350, discovered: false, visited: false, description: 'Abandoned fortress with dark secrets' },
        { id: 'cave-001', name: 'Crystal Grotto', type: 'cave', x: 350, y: 400, discovered: false, visited: false, description: 'Glowing crystals and underground rivers' },
      ];
      return mockLocations;
    },
  });

  const [playerPosition, setPlayerPosition] = useState({ x: 400, y: 300 });

  const handleLocationClick = (location: MapLocation) => {
    setSelectedLocation(location);
    onLocationClick(location);
  };

  const getLocationIcon = (type: string, discovered: boolean, visited: boolean) => {
    if (!discovered) return '🌲'; // Undiscovered
    if (!visited) return '❓'; // Discovered but not visited
    
    switch (type) {
      case 'town': return '🏘️';
      case 'dungeon': return '🏰';
      case 'forest': return '🌳';
      case 'ruin': return '🏛️';
      case 'cave': return '🕳️';
      case 'castle': return '🏯';
      case 'tower': return '🗼';
      default: return '📍';
    }
  };

  const getLocationColor = (type: string, discovered: boolean, visited: boolean) => {
    if (!discovered) return '#666';
    if (!visited) return '#FFD700';
    
    switch (type) {
      case 'town': return '#4CAF50';
      case 'dungeon': return '#F44336';
      case 'forest': return '#4CAF50';
      case 'ruin': return '#795548';
      case 'cave': return '#607D8B';
      default: return '#2196F3';
    }
  };

  if (isLoading) return (
    <div className="exploration-map">
      <div className="loading-overlay">
        <div className="loading-spinner"></div>
        <p>Mapping the realm...</p>
      </div>
    </div>
  );

  return (
    <div className="exploration-map">
      <style>{mapCSS}</style>

      <div className="map-header">
        <h3>🗺️ Exploration Map</h3>
        <div className="map-controls">
          <button onClick={() => setShowGrid(!showGrid)} className="control-button">
            {showGrid ? 'Hide Grid' : 'Show Grid'}
          </button>
          <button onClick={() => setShowLegend(!showLegend)} className="control-button">
            {showLegend ? 'Hide Legend' : 'Show Legend'}
          </button>
        </div>
      </div>

      <div className="map-container">
        <svg 
          width={mapSize.width} 
          height={mapSize.height} 
          viewBox={`0 0 ${mapSize.width} ${mapSize.height}`}
          className="map-svg"
        >
          {/* Map Background */}
          <rect width="100%" height="100%" fill="#e8f4f8" />

          {/* Grid */}
          {showGrid && (
            <>
              {Array.from({ length: mapSize.width / 50 }).map((_, i) => (
                <line 
                  key={`v-${i}`} 
                  x1={i * 50} 
                  y1={0} 
                  x2={i * 50} 
                  y2={mapSize.height} 
                  stroke="#b8d8e8" 
                  strokeWidth="1" 
                  opacity="0.3"
                />
              ))}
              {Array.from({ length: mapSize.height / 50 }).map((_, i) => (
                <line 
                  key={`h-${i}`} 
                  x1={0} 
                  y1={i * 50} 
                  x2={mapSize.width} 
                  y2={i * 50} 
                  stroke="#b8d8e8" 
                  strokeWidth="1" 
                  opacity="0.3"
                />
              ))}
            </>
          )}

          {/* Rivers */}
          <path 
            d="M100,100 Q200,150 300,120 T500,180 T700,150" 
            stroke="#4a90e2" 
            strokeWidth="8" 
            fill="none" 
            opacity="0.6"
          />

          {/* Mountains */}
          <path 
            d="M600,50 L650,100 L700,50 L750,150 L800,100" 
            stroke="#555" 
            strokeWidth="2" 
            fill="#777" 
            opacity="0.4"
          />

          {/* Forests */}
          <circle cx={200} cy={200} r={80} fill="#2ecc71" opacity="0.2" />
          <circle cx={250} cy={250} r={60} fill="#2ecc71" opacity="0.2" />
          <circle cx={180} cy={230} r={70} fill="#2ecc71" opacity="0.2" />

          {/* Player Position */}
          <circle 
            cx={playerPosition.x} 
            cy={playerPosition.y} 
            r={12} 
            fill="#FFD700" 
            stroke="#DAA520" 
            strokeWidth="3"
          />
          <text 
            x={playerPosition.x} 
            y={playerPosition.y + 30} 
            textAnchor="middle" 
            fill="#333" 
            fontSize="12"
          >
            👤 You
          </text>

          {/* Locations */}
          {locations?.map((location) => (
            <g 
              key={location.id} 
              onClick={() => handleLocationClick(location)} 
              style={{ cursor: 'pointer' }}
            >
              <circle 
                cx={location.x} 
                cy={location.y} 
                r={location.discovered ? 10 : 8} 
                fill={getLocationColor(location.type, location.discovered, location.visited)} 
                stroke="#333" 
                strokeWidth="2" 
                opacity={location.discovered ? 1 : 0.5}
              />
              <text 
                x={location.x} 
                y={location.y + 25} 
                textAnchor="middle" 
                fill="#333" 
                fontSize="10" 
                opacity={location.discovered ? 1 : 0}
              >
                {getLocationIcon(location.type, location.discovered, location.visited)}
              </text>
              {location.discovered && location.visited && (
                <text 
                  x={location.x} 
                  y={location.y - 15} 
                  textAnchor="middle" 
                  fill="#333" 
                  fontSize="10" 
                  fontWeight="bold"
                >
                  {location.name.split(' ')[0]}
                </text>
              )}
            </g>
          ))}
        </svg>

        {/* Map Legend */}
        {showLegend && (
          <div className="map-legend">
            <h4>Legend</h4>
            <div className="legend-items">
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#4CAF50' }}>🏘️</span>
                <span>Town</span>
              </div>
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#F44336' }}>🏰</span>
                <span>Dungeon</span>
              </div>
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#4CAF50' }}>🌳</span>
                <span>Forest</span>
              </div>
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#795548' }}>🏛️</span>
                <span>Ruin</span>
              </div>
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#607D8B' }}>🕳️</span>
                <span>Cave</span>
              </div>
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#FFD700' }}>❓</span>
                <span>Discovered</span>
              </div>
              <div className="legend-item">
                <span className="legend-icon" style={{ color: '#666' }}>🌲</span>
                <span>Undiscovered</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Location Details Panel */}
      {selectedLocation && (
        <div className="location-details">
          <h4>{selectedLocation.name}</h4>
          <p><strong>Type:</strong> {selectedLocation.type}</p>
          <p><strong>Status:</strong> {selectedLocation.visited ? 'Visited' : 'Discovered'}</p>
          {selectedLocation.description && (
            <p><strong>Description:</strong> {selectedLocation.description}</p>
          )}
          <button 
            onClick={() => setSelectedLocation(null)} 
            className="close-details"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
};

// CSS for the exploration map
const mapCSS = `
.exploration-map {
  background-color: white;
  border: 2px solid #8B4513;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  font-family: 'Georgia', serif;
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}

.map-header h3 {
  margin: 0;
  color: #8B4513;
}

.map-controls {
  display: flex;
  gap: 10px;
}

.control-button {
  padding: 5px 10px;
  background-color: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.control-button:hover {
  background-color: #e0e0e0;
}

.map-container {
  position: relative;
  margin-bottom: 15px;
}

.map-svg {
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #e8f4f8;
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

.map-legend {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background-color: rgba(255, 255, 255, 0.9);
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 10px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.map-legend h4 {
  margin: 0 0 10px 0;
  color: #8B4513;
  font-size: 14px;
}

.legend-items {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.legend-icon {
  font-size: 16px;
}

.location-details {
  position: absolute;
  top: 10px;
  left: 10px;
  background-color: rgba(255, 255, 255, 0.95);
  border: 1px solid #8B4513;
  border-radius: 6px;
  padding: 15px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  max-width: 250px;
  z-index: 10;
}

.location-details h4 {
  margin: 0 0 10px 0;
  color: #8B4513;
}

.close-details {
  margin-top: 10px;
  padding: 5px 10px;
  background-color: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
}

.close-details:hover {
  background-color: #e0e0e0;
}
`;

export default ExplorationMap;