import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '@fontsource/fira-sans/400.css';
import '@fontsource/fira-sans/500.css';
import '@fontsource/fira-sans/600.css';
import '@fontsource/fira-sans/700.css';
import '@fontsource/fira-sans/800.css';
import '@fontsource/fira-code/400.css';
import '@fontsource/fira-code/500.css';
import '@fontsource/fira-code/600.css';
import '@fontsource/fira-code/700.css';
import App from './App.tsx';
import './index.css';
import { DigitalTwinProvider } from './context/DigitalTwinContext.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DigitalTwinProvider>
      <App />
    </DigitalTwinProvider>
  </StrictMode>,
);
