import React, { useEffect, useState } from 'react';

interface LiveUpdatesProps {
  sessionSlug: string;
  onTranscriptUpdate: (tail: string[]) => void;
  onLockUpdate: (owner: string | null) => void;
}

const LiveUpdates: React.FC<LiveUpdatesProps> = ({ sessionSlug, onTranscriptUpdate, onLockUpdate }) => {
  useEffect(() => {
    const eventSource = new EventSource(`/api/events/${sessionSlug}`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'transcript_update') {
        onTranscriptUpdate(data.data.tail);
      } else if (data.type === 'lock_claimed') {
        onLockUpdate(data.data.owner);
      } else if (data.type === 'lock_released') {
        onLockUpdate(null);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
    };

    return () => {
      eventSource.close();
    };
  }, [sessionSlug, onTranscriptUpdate, onLockUpdate]);

  return null; // This component doesn't render anything
};

export default LiveUpdates;