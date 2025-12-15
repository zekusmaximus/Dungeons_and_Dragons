import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

interface CommitSummary {
  id: string;
  tags: string[];
  entropy_indices: number[];
  timestamp: string;
  description: string;
}

interface CommitTimelineProps {
  sessionSlug: string;
}

const CommitTimeline: React.FC<CommitTimelineProps> = ({ sessionSlug }) => {
  const [filterTag, setFilterTag] = useState('');
  const { data: commits, isLoading } = useQuery({
    queryKey: ['commits', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/history/commits`).then(r => r.json()),
  });

  const filteredCommits = commits?.filter((commit: CommitSummary) =>
    filterTag === '' || commit.tags.includes(filterTag)
  );

  return (
    <div style={{ border: '1px solid #ccc', margin: '10px', padding: '10px' }}>
      <h3>Commit Timeline</h3>
      <div>
        <label>Filter by tag: </label>
        <input
          type="text"
          value={filterTag}
          onChange={(e) => setFilterTag(e.target.value)}
          placeholder="Enter tag"
        />
      </div>
      {isLoading ? (
        <div>Loading...</div>
      ) : (
        <ul>
          {filteredCommits?.map((commit: CommitSummary) => (
            <li key={commit.id}>
              <strong>{commit.id}</strong> - {commit.description} ({commit.timestamp})
              <br />
              Tags: {commit.tags.join(', ')} | Entropy: {commit.entropy_indices.join(', ')}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default CommitTimeline;