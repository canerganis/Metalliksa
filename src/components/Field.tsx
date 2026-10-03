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

/** Space-separated aria-describedby value, or undefined when nothing is described. */
export function describedByIds(ids: FieldIds, hasHint: boolean, hasError: boolean): string | undefined {
  const parts: string[] = [];
  if (hasHint) parts.push(ids.hint);
  if (hasError) parts.push(ids.error);
  return parts.length > 0 ? parts.join(" ") : undefined;
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
  const ids = buildFieldIds(id ?? `field-${generated.replace(/:/g, "")}`);
  const controlProps: FieldControlProps = { id: ids.control };
  const describedBy = describedByIds(ids, Boolean(hint), Boolean(error));
  if (describedBy) controlProps["aria-describedby"] = describedBy;
  if (error) controlProps["aria-invalid"] = true;
  if (required) controlProps["aria-required"] = true;

  let control: React.ReactNode;
  if (typeof children === "function") {
    control = children(controlProps);
  } else if (isValidElement(children)) {
    control = cloneElement(children as React.ReactElement<Record<string, unknown>>, controlProps as unknown as Record<string, unknown>);
  } else {
    control = children;
  }

  return (
    <div className={className}>
      <label htmlFor={ids.control} className={labelClassName}>
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
