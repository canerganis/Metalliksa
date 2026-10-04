/**
 * Shell telemetry strip (Phase 9, DESIGN-9 section 3). Every cell is bound to a real source:
 * runtime config (/api/runtime-config), the 401 access flag, the Python status endpoint and the
 * module registry. A source that has not answered reads "checking"; a failed one reads "unavailable".
 * No placeholder numbers, clocks or throughput values.
 */
import React, { useEffect, useState } from "react";
import { fetchRuntimeConfig, runtimeConfigProbe, useAccessRequired, type RuntimeConfig } from "./AirgapBanner";
import { useBootSnapshot } from "./BootSequence";
import { subsystemCount } from "../services/bootSteps";
import type { PythonEngineStatus } from "../services/pythonComputationService";
import type { BootStepState } from "../utils/bootSequence";

type Tone = "ok" | "warn" | "fail" | "neutral";
export interface TelemetryCell {
  label: string;
  value: string;
  tone: Tone;
}

export interface TelemetryInputs {
  /** undefined while the first runtime-config request is in flight; null when it failed. */
  config: RuntimeConfig | null | undefined;
  accessRequired: boolean;
  engine: PythonEngineStatus | null;
  engineChecking: boolean;
  moduleCount: number;
  boot: { finished: number; total: number; stopped: boolean; rows: ReadonlyArray<{ label: string; state: BootStepState }> };
}

/** Start-up checks cell: k/N plus every step that did not pass, or "stopped" after a sign-in stop. */
function bootCell(boot: TelemetryInputs["boot"]): TelemetryCell {
  const named = (state: BootStepState) => boot.rows.filter((r) => r.state === state).map((r) => r.label);
  if (boot.stopped) return { label: "Start-up checks", value: `stopped at ${named("blocked").join(", ") || "a check"}`, tone: "fail" };
  const groups: Array<[string, string[]]> = [
    ["unavailable", named("unavailable")],
    ["timed out", named("timed-out")],
    ["limited", named("limited")],
  ];
  const parts = [`${boot.finished}/${boot.total}`, ...groups.filter(([, n]) => n.length).map(([word, n]) => `${word}: ${n.join(", ")}`)];
  const tone = groups[0][1].length || groups[1][1].length ? "fail" : groups[2][1].length ? "warn" : "neutral";
  return { label: "Start-up checks", value: parts.join(" · "), tone };
}

/** Pure mapping from source values to cells; tested without a DOM. */
export function telemetryCells(input: TelemetryInputs): TelemetryCell[] {
  const { config, engine } = input;
  const pending = config === undefined;
  const subsystems = engine?.online ? subsystemCount(engine) : null;
  const cells: TelemetryCell[] = [
    {
      label: "Air-gap",
      value: pending ? "checking" : !config ? "unavailable" : config.airgapped ? `ON${config.blockedServices.length ? ` · ${config.blockedServices.length} cut` : ""}` : "OFF",
      tone: pending ? "neutral" : !config ? "fail" : config.airgapped ? "warn" : "ok",
    },
    {
      label: "Access",
      value: input.accessRequired ? "sign-in required" : pending ? "checking" : config ? "accepted" : "unavailable",
      tone: input.accessRequired || (!pending && !config) ? "fail" : pending ? "neutral" : "ok",
    },
    {
      label: "Engine",
      value: engine?.online
        ? `online · ${engine.pythonVersion ? `Python ${engine.pythonVersion}` : "version not reported"}`
        : input.engineChecking && !engine
          ? "checking"
          : "unavailable",
      tone: engine?.online ? "ok" : input.engineChecking && !engine ? "neutral" : "fail",
    },
    {
      label: "Subsystems",
      value: subsystems
        ? `${subsystems.available}/${subsystems.total}`
        : engine?.online
          ? "not reported"
          : input.engineChecking && !engine
            ? "checking"
            : "unavailable",
      tone: subsystems
        ? subsystems.available === subsystems.total ? "ok" : "warn"
        : engine?.online ? "warn" : input.engineChecking && !engine ? "neutral" : "fail",
    },
    {
      label: "Modules",
      value: input.moduleCount > 0 ? `${input.moduleCount} registered` : "unavailable",
      tone: input.moduleCount > 0 ? "neutral" : "fail",
    },
    bootCell(input.boot),
  ];
  return cells;
}

export function TelemetryStrip({ engine, engineChecking, moduleCount }: { engine: PythonEngineStatus | null; engineChecking: boolean; moduleCount: number }) {
  const accessRequired = useAccessRequired();
  const boot = useBootSnapshot();
  const [config, setConfig] = useState<RuntimeConfig | null | undefined>(undefined);
  const configStep = boot.rows[0]?.state;
  useEffect(() => {
    // Wait for the boot config check instead of sending a parallel request; afterwards this returns the cache.
    if (configStep === "pending" || configStep === "running") return undefined;
    let live = true;
    void fetchRuntimeConfig().then((cfg) => {
      if (live) setConfig(runtimeConfigProbe().loaded ? cfg : null);
    });
    return () => {
      live = false;
    };
  }, [accessRequired, configStep]);

  const cells = telemetryCells({
    config,
    accessRequired,
    engine,
    engineChecking,
    moduleCount,
    boot: { finished: boot.finished, total: boot.total, stopped: boot.phase === "stopped", rows: boot.rows },
  });
  return (
    <footer className="mk-telemetry" aria-label="System telemetry">
      <dl>
        {cells.map((cell) => (
          <div key={cell.label}>
            <dt>{cell.label}</dt>
            <dd data-tone={cell.tone}>{cell.value}</dd>
          </div>
        ))}
      </dl>
    </footer>
  );
}
