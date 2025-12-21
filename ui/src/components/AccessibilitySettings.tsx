import React, { useState, useEffect } from 'react';

interface AccessibilitySettingsProps {
  onClose: () => void;
  onApply: (settings: AccessibilitySettings) => void;
}

interface AccessibilitySettings {
  fontSize: string;
  highContrast: boolean;
  dyslexiaFriendly: boolean;
  colorBlindMode: string;
  textToSpeech: boolean;
  reduceMotion: boolean;
  darkMode: boolean;
}

const AccessibilitySettings: React.FC<AccessibilitySettingsProps> = ({ onClose, onApply }) => {
  const [settings, setSettings] = useState<AccessibilitySettings>({
    fontSize: 'medium',
    highContrast: false,
    dyslexiaFriendly: false,
    colorBlindMode: 'none',
    textToSpeech: false,
    reduceMotion: false,
    darkMode: false
  });

  // Load saved settings from localStorage
  useEffect(() => {
    const savedSettings = localStorage.getItem('accessibilitySettings');
    if (savedSettings) {
      try {
        setSettings(JSON.parse(savedSettings));
      } catch (e) {
        console.error('Failed to load accessibility settings:', e);
      }
    }
  }, []);

  // Apply settings to the document
  useEffect(() => {
    applySettingsToDocument(settings);
  }, [settings]);

  const applySettingsToDocument = (settings: AccessibilitySettings) => {
    const root = document.documentElement;
    
    // Remove all accessibility classes first
    root.classList.remove('high-contrast', 'dyslexia-friendly', 'color-blind-none');
    root.classList.remove('color-blind-protanopia', 'color-blind-deuteranopia');
    root.classList.remove('color-blind-tritanopia', 'color-blind-achromatopsia');
    root.classList.remove('reduce-motion', 'dark-mode');
    
    // Apply font size
    root.style.setProperty('--font-size', getFontSizeValue(settings.fontSize));
    
    // Apply other settings
    if (settings.highContrast) root.classList.add('high-contrast');
    if (settings.dyslexiaFriendly) root.classList.add('dyslexia-friendly');
    if (settings.reduceMotion) root.classList.add('reduce-motion');
    if (settings.darkMode) root.classList.add('dark-mode');
    
    // Apply color blind mode
    if (settings.colorBlindMode !== 'none') {
      root.classList.add(`color-blind-${settings.colorBlindMode}`);
    } else {
      root.classList.add('color-blind-none');
    }
  };

  const getFontSizeValue = (size: string) => {
    const sizes = {
      'small': '14px',
      'medium': '16px',
      'large': '18px',
      'xlarge': '20px'
    };
    return sizes[size as keyof typeof sizes] || '16px';
  };

  const handleSettingChange = (setting: keyof AccessibilitySettings, value: string | boolean) => {
    setSettings(prev => ({
      ...prev,
      [setting]: value
    }));
  };

  const handleSave = () => {
    // Save settings to localStorage
    localStorage.setItem('accessibilitySettings', JSON.stringify(settings));
    
    // Apply settings
    onApply(settings);
    onClose();
  };

  const handleReset = () => {
    const defaultSettings: AccessibilitySettings = {
      fontSize: 'medium',
      highContrast: false,
      dyslexiaFriendly: false,
      colorBlindMode: 'none',
      textToSpeech: false,
      reduceMotion: false,
      darkMode: false
    };
    
    setSettings(defaultSettings);
    localStorage.setItem('accessibilitySettings', JSON.stringify(defaultSettings));
    applySettingsToDocument(defaultSettings);
  };

  return (
    <div className="accessibility-settings">
      <style>{accessibilityCSS}</style>

      <div className="settings-header">
        <h2>⚙️ Accessibility Settings</h2>
        <button onClick={onClose} className="close-button">×</button>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <h3>Visual Settings</h3>

          <div className="setting-item">
            <label htmlFor="fontSize">Font Size:</label>
            <select
              id="fontSize"
              value={settings.fontSize}
              onChange={(e) => handleSettingChange('fontSize', e.target.value)}
            >
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
              <option value="xlarge">Extra Large</option>
            </select>
          </div>

          <div className="setting-item">
            <label htmlFor="highContrast">High Contrast Mode:</label>
            <input
              type="checkbox"
              id="highContrast"
              checked={settings.highContrast}
              onChange={(e) => handleSettingChange('highContrast', e.target.checked)}
            />
          </div>

          <div className="setting-item">
            <label htmlFor="dyslexiaFriendly">Dyslexia Friendly Font:</label>
            <input
              type="checkbox"
              id="dyslexiaFriendly"
              checked={settings.dyslexiaFriendly}
              onChange={(e) => handleSettingChange('dyslexiaFriendly', e.target.checked)}
            />
          </div>

          <div className="setting-item">
            <label htmlFor="colorBlindMode">Color Blind Mode:</label>
            <select
              id="colorBlindMode"
              value={settings.colorBlindMode}
              onChange={(e) => handleSettingChange('colorBlindMode', e.target.value)}
            >
              <option value="none">None</option>
              <option value="protanopia">Protanopia (Red-Weak)</option>
              <option value="deuteranopia">Deuteranopia (Green-Weak)</option>
              <option value="tritanopia">Tritanopia (Blue-Weak)</option>
              <option value="achromatopsia">Achromatopsia (Monochrome)</option>
            </select>
          </div>

          <div className="setting-item">
            <label htmlFor="darkMode">Dark Mode:</label>
            <input
              type="checkbox"
              id="darkMode"
              checked={settings.darkMode}
              onChange={(e) => handleSettingChange('darkMode', e.target.checked)}
            />
          </div>
        </div>

        <div className="settings-section">
          <h3>Motion & Animation</h3>

          <div className="setting-item">
            <label htmlFor="reduceMotion">Reduce Motion:</label>
            <input
              type="checkbox"
              id="reduceMotion"
              checked={settings.reduceMotion}
              onChange={(e) => handleSettingChange('reduceMotion', e.target.checked)}
            />
          </div>
        </div>

        <div className="settings-section">
          <h3>Assistive Features</h3>

          <div className="setting-item">
            <label htmlFor="textToSpeech">Text-to-Speech (Experimental):</label>
            <input
              type="checkbox"
              id="textToSpeech"
              checked={settings.textToSpeech}
              onChange={(e) => handleSettingChange('textToSpeech', e.target.checked)}
              disabled
            />
            <span className="feature-note">Coming soon</span>
          </div>
        </div>

        <div className="settings-section">
          <h3>Preview</h3>
          <div className="preview-area">
            <p>This text demonstrates how your settings will appear in the game.</p>
            <p>The quick brown fox jumps over the lazy dog. 1234567890</p>
            <div className="preview-buttons">
              <button className="preview-button">Sample Button</button>
              <button className="preview-button primary">Primary Action</button>
            </div>
          </div>
        </div>
      </div>

      <div className="settings-footer">
        <button onClick={handleReset} className="reset-button">
          Reset to Defaults
        </button>
        <button onClick={handleSave} className="save-button">
          Save Settings
        </button>
      </div>
    </div>
  );
};

// CSS for accessibility settings
const accessibilityCSS = `
.accessibility-settings {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 600px;
  max-width: 90vw;
  background-color: white;
  border: 2px solid #8B4513;
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  z-index: 1003;
  font-family: 'Georgia', serif;
  max-height: 80vh;
  overflow-y: auto;
}

.settings-header {
  background-color: #8B4513;
  color: white;
  padding: 15px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 10px 10px 0 0;
}

.settings-header h2 {
  margin: 0;
  font-size: 18px;
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

.settings-content {
  padding: 20px;
}

.settings-section {
  margin-bottom: 25px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.settings-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.settings-section h3 {
  color: #8B4513;
  margin-bottom: 15px;
  font-size: 16px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f9f5f0;
  border-radius: 6px;
}

.setting-item label {
  font-weight: bold;
  color: #333;
}

.setting-item select,
.setting-item input[type="checkbox"] {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.setting-item input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.feature-note {
  font-size: 12px;
  color: #666;
  margin-left: 10px;
  font-style: italic;
}

.preview-area {
  background-color: #f0f0f0;
  padding: 15px;
  border-radius: 6px;
  margin-top: 15px;
}

.preview-area p {
  margin: 10px 0;
}

.preview-buttons {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.preview-button {
  padding: 8px 15px;
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
}

.preview-button.primary {
  background-color: #8B4513;
  color: white;
  border-color: #8B4513;
}

.settings-footer {
  background-color: #f0f0f0;
  padding: 15px 20px;
  border-radius: 0 0 10px 10px;
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.reset-button {
  padding: 10px 20px;
  background-color: #e57373;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.reset-button:hover {
  background-color: #ef5350;
}

.save-button {
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.save-button:hover {
  background-color: #45a049;
}

/* Accessibility modes */
.high-contrast {
  --background-color: #000;
  --text-color: #fff;
  --primary-color: #00f;
  --secondary-color: #ff0;
}

.dyslexia-friendly {
  font-family: 'OpenDyslexic', 'Arial', sans-serif;
  letter-spacing: 0.1em;
  line-height: 1.6;
}

.color-blind-protanopia {
  /* Protanopia simulation */
}

.color-blind-deuteranopia {
  /* Deuteranopia simulation */
}

.color-blind-tritanopia {
  /* Tritanopia simulation */
}

.color-blind-achromatopsia {
  filter: grayscale(100%) contrast(200%);
}

.reduce-motion {
  /* Disable animations */
  * {
    animation: none !important;
    transition: none !important;
  }
}

.dark-mode {
  --background-color: #121212;
  --text-color: #e0e0e0;
  --primary-color: #bb86fc;
  --secondary-color: #03dac6;
}
`;

export default AccessibilitySettings;