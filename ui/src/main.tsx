import * as React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './style.css';
import { installApiFetchShim } from './apiBase';

installApiFetchShim();

createRoot(document.getElementById('app')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
