import React from 'react';

interface Clock {
  id: string;
  name: string;
  segments: number;
  filled: number;
}

interface ClockVisualizationProps {
  clocks: Clock[];
}

const ClockVisualization: React.FC<ClockVisualizationProps> = ({ clocks }) => {
  return (
    <div>
      {clocks.map((clock) => (
        <div key={clock.id}>
          <h4>{clock.name}</h4>
          <div style={{ display: 'flex' }}>
            {Array.from({ length: clock.segments }, (_, i) => (
              <div
                key={i}
                style={{
                  width: '20px',
                  height: '20px',
                  border: '1px solid black',
                  backgroundColor: i < clock.filled ? 'black' : 'white',
                  margin: '2px',
                }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ClockVisualization;