import React from "react";
import { CALPHADMultiComponentStudio } from "./CALPHADMultiComponentStudio";

// Phase-diagram module view: the multi-component CALPHAD studio (pycalphad equilibrium,
// MatCalc open TDB databases and Scheil solidification).
export const PhaseDiagramViewer: React.FC = () => {
  return (
    <div id="phase-diagram-viewer" className="space-y-6 animate-fadeIn">
      <CALPHADMultiComponentStudio />
    </div>
  );
};
