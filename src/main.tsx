import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '@fontsource/fira-sans/latin-400.css';
import '@fontsource/fira-sans/latin-ext-400.css';
import '@fontsource/fira-sans/latin-500.css';
import '@fontsource/fira-sans/latin-ext-500.css';
import '@fontsource/fira-sans/latin-600.css';
import '@fontsource/fira-sans/latin-ext-600.css';
import '@fontsource/fira-sans/latin-700.css';
import '@fontsource/fira-sans/latin-ext-700.css';
import '@fontsource/fira-sans/latin-800.css';
import '@fontsource/fira-sans/latin-ext-800.css';
import '@fontsource/fira-code/latin-400.css';
import '@fontsource/fira-code/latin-ext-400.css';
import '@fontsource/fira-code/latin-500.css';
import '@fontsource/fira-code/latin-ext-500.css';
import '@fontsource/fira-code/latin-600.css';
import '@fontsource/fira-code/latin-ext-600.css';
import '@fontsource/fira-code/latin-700.css';
import '@fontsource/fira-code/latin-ext-700.css';
import App from './App.tsx';
import './index.css';
import './styles/boot.css';
import { installApiUnauthorizedWatcher } from './components/AirgapBanner.tsx';
import { DigitalTwinProvider } from './context/DigitalTwinContext.tsx';

installApiUnauthorizedWatcher();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DigitalTwinProvider>
      <App />
    </DigitalTwinProvider>
  </StrictMode>,
);
