import React, { useEffect } from 'react';
import { createApiEventSource } from '../apiBase';

interface LiveUpdatesProps {
  sessionSlug: string;
  onTranscriptUpdate: (lines: string[]) => void;
  onChangelogUpdate?: (lines: string[]) => void;
  onRollUpdate?: (rolls: { turn: number; items: any[] }) => void;
}

const LiveUpdates: React.FC<LiveUpdatesProps> = ({ sessionSlug, onTranscriptUpdate, onChangelogUpdate, onRollUpdate }) => {
  useEffect(() => {
    const eventSource = createApiEventSource(`/api/events/${sessionSlug}`);

    const handleUpdate = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data || '{}');
        if (payload.transcript?.lines?.length) {
          onTranscriptUpdate(payload.transcript.lines);
        }
        if (payload.changelog?.lines?.length && onChangelogUpdate) {
          onChangelogUpdate(payload.changelog.lines);
        }
        if (payload.rolls && payload.rolls.items && onRollUpdate) {
          onRollUpdate(payload.rolls);
        }
      } catch (err) {
        console.error('Failed to parse SSE payload', err);
      }
    };

    eventSource.addEventListener('update', handleUpdate);

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
    };

    return () => {
      eventSource.removeEventListener('update', handleUpdate);
      eventSource.close();
    };
  }, [sessionSlug, onTranscriptUpdate]);

  return null; // No UI
};

export default LiveUpdates;
