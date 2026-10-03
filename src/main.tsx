import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
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
