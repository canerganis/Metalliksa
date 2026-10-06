import React from "react";
import { Activity } from "lucide-react";
import { UNAVAILABLE_TEXT } from "../../utils/hardnessConversion";
import {
  type BuildJobKineticsLike,
  buildJobCctRow,
  buildJobKineticsAvailability,
  buildJobMartensiteText,
  kineticsHardnessText,
} from "../../utils/kineticsHardnessDisplay";

// Phase-transformation kinetics of an LPBF build job (python/lpbf_build_job_solver.py build_job_kinetics). Python
// decides availability, the CCT row for the build cooling rate and whether a martensite fraction / verdict may be
// reported; this panel only displays those decisions. Anything withheld shows "Unavailable" with Python's reason.

const KineticsMetric: React.FC<{ label: string; value: string; hint?: string }> = ({ label, value, hint }) => (
  <div className="rounded-lg border px-2 py-1.5 border-[#162032] bg-[#060a12]" data-kinetics-metric={label}>
    <div className="text-[9px] text-slate-500 uppercase">{label}</div>
    <div className="text-[12px] text-white font-bold truncate">{value}</div>
    {hint && <div className="text-[9px] text-slate-500">{hint}</div>}
  </div>
);

/** Python reasons have no final period; add one for display. */
const sentence = (text: string): string => (/[.!?]$/.test(text) ? text : `${text}.`);

export const BuildJobKineticsPanel: React.FC<{ kinetics: BuildJobKineticsLike | null | undefined }> = ({ kinetics }) => {
  if (!kinetics) return null;
  const availability = buildJobKineticsAvailability(kinetics);
  const cct = buildJobCctRow(kinetics);
  const hardness = kineticsHardnessText(cct.row);
  const martensite = buildJobMartensiteText(kinetics);
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Activity className="w-4 h-4 text-rose-400" />
        <h3 className="text-xs font-bold text-white">Phase Transformation Kinetics</h3>
      </div>
      {availability.available ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <KineticsMetric
              label="Primary Phase"
              value={cct.row?.primaryMicrostructure || UNAVAILABLE_TEXT}
              hint={
                !cct.row
                  ? "No CCT row selected"
                  : cct.row.primaryMicrostructure
                    ? "From the CCT row below"
                    : sentence(cct.row.unavailableReason || "No primary phase in the CCT row")
              }
            />
            <KineticsMetric label="Martensite" value={martensite.value} hint={martensite.hint} />
            <KineticsMetric
              label="Hardness (HRC)"
              value={hardness.hrcValue}
              hint={cct.row ? "Predicted at RT" : "No CCT row selected"}
            />
            <KineticsMetric
              label="Hardness (HV)"
              value={hardness.hvValue}
              hint={
                !cct.row
                  ? "No CCT row selected"
                  : hardness.hvValue === UNAVAILABLE_TEXT
                    ? "No verified HV conversion"
                    : "ASTM E140 from HRC"
              }
            />
          </div>
          <p className="text-[9px] text-slate-400 mt-1" data-kinetics-line="cct">{cct.label}</p>
          {martensite.verdict ? (
            <p className="text-[9px] text-slate-500 mt-1" data-kinetics-line="verdict">{martensite.verdict}</p>
          ) : (
            <p className="text-[9px] text-slate-400 mt-1" data-kinetics-line="martensite">
              Martensite and verdict: {martensite.reason}
            </p>
          )}
        </>
      ) : (
        <>
          <KineticsMetric label="Kinetics" value={UNAVAILABLE_TEXT} hint="Reason below" />
          <p className="text-[9px] text-slate-400 mt-1" data-kinetics-line="reason">{availability.reason}</p>
        </>
      )}
    </div>
  );
};
