import React from "react";
import { meltPoolExtentInfo, type MeltPoolExtentFields } from "../utils/meltPoolExtentStatus";

/** Amber label shown next to melt-pool W/D/L whenever extentStatus is not "computed". Renders nothing otherwise. */
export const MeltPoolExtentNotice: React.FC<{ geometry: MeltPoolExtentFields | null | undefined; className?: string }> = ({
  geometry,
  className,
}) => {
  const info = meltPoolExtentInfo(geometry);
  if (info.computed) return null;
  return (
    <div
      className={`rounded border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-200 ${className ?? ""}`}
      data-extent-status={info.status}
    >
      <span className="font-bold font-mono">{info.status}</span>
      {" — "}
      {info.description}
      {info.note ? <span className="block opacity-80">{info.note}</span> : null}
    </div>
  );
};
