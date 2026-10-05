// Tiny typed helpers to mutate a parsed JSON document by path in tests (no `any`).
export type JsonPath = readonly (string | number)[];
type Container = Record<string | number, unknown>;

function parent(doc: unknown, path: JsonPath): Container {
  let cursor = doc as Container;
  for (const key of path.slice(0, -1)) cursor = cursor[key] as Container;
  return cursor;
}

export function setPath(doc: unknown, path: JsonPath, value: unknown): void {
  parent(doc, path)[path[path.length - 1]] = value;
}

export function deletePath(doc: unknown, path: JsonPath): void {
  delete parent(doc, path)[path[path.length - 1]];
}

export function getPath(doc: unknown, path: JsonPath): unknown {
  return parent(doc, path)[path[path.length - 1]];
}
