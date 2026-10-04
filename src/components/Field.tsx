/**
 * Label + control wrapper with generated ids and accessible hint/error wiring.
 *
 * Render-prop usage (any control):
 *   <Field label="Temperature" unit="K" hint="Between 300 and 2000" error={err} required>
 *     {(p) => <input type="number" {...p} value={v} onChange={...} />}
 *   </Field>
 *
 * Children-cloning usage (single element child):
 *   <Field label="Alloy"><select>...</select></Field>
 *
 * `p` carries id, aria-describedby, aria-invalid, aria-required. Visual styling is left to the caller.
 */
import React, { cloneElement, isValidElement, useId } from "react";

export interface FieldControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  "aria-required"?: true;
}

export interface FieldIds {
  control: string;
  hint: string;
  error: string;
}

/** Deterministic id set derived from one base id. */
export function buildFieldIds(baseId: string): FieldIds {
  return { control: baseId, hint: `${baseId}-hint`, error: `${baseId}-error` };
}

/**
 * aria-describedby value, or undefined when nothing is described. Only the hint is referenced:
 * the error paragraph is role="alert" and is announced by itself (referencing it would double announce).
 */
export function describedByIds(ids: FieldIds, hasHint: boolean): string | undefined {
  return hasHint ? ids.hint : undefined;
}

/** Merges space-separated id lists, dropping blanks and duplicates (existing ids first). */
export function mergeIdList(...lists: Array<string | undefined>): string | undefined {
  const seen: string[] = [];
  for (const list of lists) {
    for (const part of (list ?? "").split(/\s+/)) if (part && !seen.includes(part)) seen.push(part);
  }
  return seen.length > 0 ? seen.join(" ") : undefined;
}

export interface FieldProps {
  label: React.ReactNode;
  /** Explicit control id; otherwise generated with useId. */
  id?: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  unit?: React.ReactNode;
  className?: string;
  labelClassName?: string;
  children: React.ReactNode | ((props: FieldControlProps) => React.ReactNode);
}

export const Field: React.FC<FieldProps> = ({
  label,
  id,
  hint,
  error,
  required = false,
  unit,
  className,
  labelClassName,
  children,
}) => {
  const generated = useId();
  const baseId = id ?? `field-${generated.replace(/:/g, "")}`;
  const childProps: Record<string, unknown> = isValidElement(children)
    ? ((children as React.ReactElement<Record<string, unknown>>).props ?? {})
    : {};
  // A cloned child's own id wins so its existing references keep working; the label follows it.
  const ownId = typeof childProps.id === "string" && childProps.id ? childProps.id : undefined;
  const ids = buildFieldIds(baseId);
  const controlId = typeof children !== "function" && ownId ? ownId : ids.control;
  const controlProps: FieldControlProps = { id: controlId };
  const describedBy = describedByIds(ids, Boolean(hint));
  if (describedBy) controlProps["aria-describedby"] = describedBy;
  if (error) controlProps["aria-invalid"] = true;
  if (required) controlProps["aria-required"] = true;

  let control: React.ReactNode;
  if (typeof children === "function") {
    control = children(controlProps);
  } else if (isValidElement(children)) {
    const merged: Record<string, unknown> = { ...controlProps };
    const mergedDescribedBy = mergeIdList(childProps["aria-describedby"] as string | undefined, describedBy);
    if (mergedDescribedBy) merged["aria-describedby"] = mergedDescribedBy;
    control = cloneElement(children as React.ReactElement<Record<string, unknown>>, merged);
  } else {
    control = children;
  }

  return (
    <div className={className}>
      <label htmlFor={controlId} className={labelClassName}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      <div className="flex items-center gap-2">
        {control}
        {unit ? <span data-field-unit="">{unit}</span> : null}
      </div>
      {hint ? <p id={ids.hint}>{hint}</p> : null}
      {error ? <p id={ids.error} role="alert">{error}</p> : null}
    </div>
  );
};
