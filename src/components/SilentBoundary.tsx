import React from "react";

/**
 * Error boundary for optional chrome (the lazy telemetry strip): if its chunk fails to load (stale
 * chunk after a rebuild) or it throws, render nothing instead of unmounting the whole App.
 * There is no root boundary above App.
 */
export class SilentBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  // Same pattern as ModuleBoundary: the project does not ship @types/react class members.
  declare props: { children: React.ReactNode };
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
