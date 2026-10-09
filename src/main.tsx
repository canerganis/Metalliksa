import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '@fontsource/newsreader/latin-300.css';
import '@fontsource/newsreader/latin-ext-300.css';
import '@fontsource/newsreader/latin-300-italic.css';
import '@fontsource/fira-sans/latin-300.css';
import '@fontsource/fira-sans/latin-ext-300.css';
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
import { IS_STATIC_DEMO } from './demo/flag.ts';

function mount() {
  installApiUnauthorizedWatcher();
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

if (IS_STATIC_DEMO) {
  // Static demo only: answer /api calls from recorded snapshots before anything wraps or calls fetch.
  // IS_STATIC_DEMO is a build-time constant, so this branch and the demo chunk are absent from normal builds.
  void import('./demo/staticDemo.ts').then(demo => { demo.installDemoFetch(); mount(); });
} else {
  mount();
}
