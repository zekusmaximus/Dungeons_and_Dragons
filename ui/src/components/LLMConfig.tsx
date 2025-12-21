import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';

interface LLMConfig {
  api_key_set: boolean;
  current_model: string;
  base_url: string;
  temperature: number;
  max_tokens: number;
  source: string;
}

interface LLMConfigProps {
  onConfigSaved: () => void;
}

const fetchLLMConfig = async (): Promise<LLMConfig> => {
  const response = await fetch('/api/llm/config');
  if (!response.ok) throw new Error('Failed to fetch LLM config');
  return response.json();
};

const saveLLMConfig = async (config: { api_key: string; base_url?: string; model?: string }): Promise<LLMConfig> => {
  const response = await fetch('/api/llm/config', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error('Failed to save LLM config');
  return response.json();
};

const LLMConfig: React.FC<LLMConfigProps> = ({ onConfigSaved }) => {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('https://api.openai.com/v1');
  const [model, setModel] = useState('gpt-4o');
  const [showConfig, setShowConfig] = useState(false);

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['llmConfig'],
    queryFn: fetchLLMConfig,
  });

  const mutation = useMutation({
    mutationFn: saveLLMConfig,
    onSuccess: () => {
      onConfigSaved();
      setShowConfig(false);
    },
  });

  React.useEffect(() => {
    if (config) {
      setBaseUrl(config.base_url);
      setModel(config.current_model);
    }
  }, [config]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({ api_key: apiKey, base_url: baseUrl, model });
  };

  if (isLoading) return <div>Loading LLM config...</div>;
  if (error) return <div>Error loading LLM config</div>;

  return (
    <div className="llm-config">
      <h3>LLM Configuration</h3>
      <div className="config-status">
        {config?.api_key_set ? (
          <span className="status-active">✓ LLM API configured</span>
        ) : (
          <span className="status-inactive">✗ LLM API not configured</span>
        )}
        <span className="config-source">
          Using {config?.source === 'file' ? 'saved' : 'environment'} settings
        </span>
        <button onClick={() => setShowConfig(!showConfig)}>
          {showConfig ? 'Hide' : 'Configure'}
        </button>
      </div>
      <p className="config-note">
        API keys are stored locally in <code>.dm_llm_config.json</code> at the repo root and are not returned by the API.
        Base URL and model defaults come from environment variables if no saved config exists.
      </p>

      {showConfig && (
        <form onSubmit={handleSubmit} className="config-form">
          <div className="form-group">
            <label htmlFor="apiKey">API Key:</label>
            <input
              type="password"
              id="apiKey"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
              placeholder="Enter your LLM API key"
            />
          </div>

          <div className="form-group">
            <label htmlFor="baseUrl">Base URL:</label>
            <input
              type="url"
              id="baseUrl"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div className="form-group">
            <label htmlFor="model">Model:</label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="gemini-pro">Gemini Pro</option>
            </select>
          </div>

          <button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving...' : 'Save Configuration'}
          </button>

          {mutation.error && (
            <div className="error-message">
              Error: {mutation.error.message}
            </div>
          )}

          {mutation.isSuccess && (
            <div className="success-message">
              Configuration saved successfully!
            </div>
          )}
        </form>
      )}
    </div>
  );
};

export default LLMConfig;
