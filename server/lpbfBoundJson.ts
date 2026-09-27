/** Bounded JSON reader for the frozen Python v1 producer serialization. */
export const MAX_GPU_JSON_BYTES = 1024 * 1024;
const MAX_DEPTH = 128;
const MAX_NODES = 200_000;

type Node =
  | { kind: 'primitive'; value: null | boolean; raw: string }
  | { kind: 'number'; value: number; raw: string; integer: boolean }
  | { kind: 'string'; value: string; raw: string }
  | { kind: 'array'; items: Node[] }
  | { kind: 'object'; entries: Array<[string, string, Node]> };

export interface BoundedJsonDocument<T = unknown> {
  value: T;
  /** Python json.dumps-compatible canonicalizer; unsupported token spellings fail closed. */
  pythonCompactJson(options?: { omitTopLevelKey?: string }): string;
}

function fail(): never { throw new Error('Invalid or over-budget GPU archive JSON'); }

function codePointCompare(a: string, b: string): number {
  const left = Array.from(a, ch => ch.codePointAt(0)!);
  const right = Array.from(b, ch => ch.codePointAt(0)!);
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    if (left[i] !== right[i]) return left[i] - right[i];
  }
  return left.length - right.length;
}

function pythonString(value: string): string {
  let output = '"';
  const hex4 = (unit: number) => unit.toString(16).padStart(4, '0');
  for (let i = 0; i < value.length; i++) {
    const unit = value.charCodeAt(i);
    if (unit === 34) output += '\\"';
    else if (unit === 92) output += '\\\\';
    else if (unit === 8) output += '\\b';
    else if (unit === 9) output += '\\t';
    else if (unit === 10) output += '\\n';
    else if (unit === 12) output += '\\f';
    else if (unit === 13) output += '\\r';
    else if (unit < 0x20 || unit > 0x7e) {
      if (unit >= 0xd800 && unit <= 0xdbff && i + 1 < value.length) {
        const low = value.charCodeAt(i + 1);
        if (low >= 0xdc00 && low <= 0xdfff) { output += `\\u${hex4(unit)}\\u${hex4(low)}`; i++; continue; }
      }
      output += `\\u${hex4(unit)}`;
    } else output += value[i];
  }
  return `${output}\"`;
}

function pythonFloat(raw: string, value: number): string {
  if (value === 0) return raw.startsWith('-') ? '-0.0' : '0.0';
  const negative = value < 0, source = Math.abs(value).toString().toLowerCase();
  const [mantissa, exponentRaw] = source.split('e');
  const exponentPart = exponentRaw === undefined ? 0 : Number(exponentRaw);
  const point = mantissa.indexOf('.');
  const decimal = point < 0 ? mantissa.length : point;
  let digits = mantissa.replace('.', '');
  let position = decimal + exponentPart;
  const leading = digits.match(/^0+/)?.[0].length ?? 0;
  digits = digits.slice(leading); position -= leading;
  digits = digits.replace(/0+$/, '') || '0';
  const exponent = position - 1;
  let normalized: string;
  if (exponent < -4 || exponent >= 16) {
    const fraction = digits.length > 1 ? `.${digits.slice(1)}` : '';
    normalized = `${digits[0]}${fraction}e${exponent >= 0 ? '+' : '-'}${String(Math.abs(exponent)).padStart(2, '0')}`;
  } else if (position <= 0) {
    normalized = `0.${'0'.repeat(-position)}${digits}`;
  } else if (position >= digits.length) {
    normalized = `${digits}${'0'.repeat(position - digits.length)}.0`;
  } else {
    normalized = `${digits.slice(0, position)}.${digits.slice(position)}`;
  }
  return `${negative ? '-' : ''}${normalized}`;
}

export function parseBoundedJson<T = unknown>(source: string, maxBytes = MAX_GPU_JSON_BYTES): BoundedJsonDocument<T> {
  if (typeof source !== 'string' || !Number.isSafeInteger(maxBytes) || maxBytes < 1
    || Buffer.byteLength(source, 'utf8') > maxBytes) fail();
  let offset = 0, nodes = 0;
  const ws = () => { while (source[offset] === ' ' || source[offset] === '\n' || source[offset] === '\r' || source[offset] === '\t') offset++; };
  const stringToken = (): { value: string; raw: string } => {
    const start = offset;
    if (source[offset++] !== '"') fail();
    while (offset < source.length) {
      const c = source.charCodeAt(offset++);
      if (c === 34) {
        const raw = source.slice(start, offset);
        let value: unknown;
        try { value = JSON.parse(raw); } catch { fail(); }
        if (typeof value !== 'string') fail();
        return { value, raw };
      }
      if (c < 0x20) fail();
      if (c === 92) {
        if (offset >= source.length) fail();
        const esc = source[offset++];
        if ('"\\/bfnrt'.includes(esc)) continue;
        if (esc !== 'u' || !/^[0-9a-fA-F]{4}$/.test(source.slice(offset, offset + 4))) fail();
        offset += 4;
      }
    }
    return fail();
  };
  const parse = (depth: number): Node => {
    if (depth > MAX_DEPTH || ++nodes > MAX_NODES) fail();
    ws();
    const c = source[offset];
    if (c === '"') {
      const token = stringToken(); return { kind: 'string', ...token };
    }
    if (c === '{') {
      offset++; ws(); const entries: Array<[string, string, Node]> = []; const seen = new Set<string>();
      if (source[offset] === '}') { offset++; return { kind: 'object', entries }; }
      while (true) {
        ws(); if (source[offset] !== '"') fail();
        const key = stringToken();
        if (seen.has(key.value)) fail();
        seen.add(key.value); ws(); if (source[offset++] !== ':') fail();
        entries.push([key.value, key.raw, parse(depth + 1)]); ws();
        const end = source[offset++]; if (end === '}') break; if (end !== ',') fail();
      }
      return { kind: 'object', entries };
    }
    if (c === '[') {
      offset++; ws(); const items: Node[] = [];
      if (source[offset] === ']') { offset++; return { kind: 'array', items }; }
      while (true) {
        items.push(parse(depth + 1)); ws();
        const end = source[offset++]; if (end === ']') break; if (end !== ',') fail();
      }
      return { kind: 'array', items };
    }
    for (const [token, value] of [['true', true], ['false', false], ['null', null]] as const) {
      if (source.startsWith(token, offset)) { offset += token.length; return { kind: 'primitive', value, raw: token }; }
    }
    const match = source.slice(offset).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (match) {
      offset += match[0].length;
      const value = Number(match[0]);
      if (!Number.isFinite(value) || (!/[.eE]/.test(match[0]) && !Number.isSafeInteger(value))) fail();
      return { kind: 'number', value, raw: match[0], integer: !/[.eE]/.test(match[0]) };
    }
    return fail();
  };
  const root = parse(0); ws(); if (offset !== source.length) fail();

  const materialize = (node: Node): unknown => {
    if (node.kind === 'primitive' || node.kind === 'number' || node.kind === 'string') return node.value;
    if (node.kind === 'array') return node.items.map(materialize);
    const object: Record<string, unknown> = Object.create(null);
    for (const [key, , child] of node.entries) Object.defineProperty(object, key, { value: materialize(child), enumerable: true, writable: true, configurable: true });
    return object;
  };
  const stringify = (node: Node, omit?: string, top = false): string => {
    if (node.kind === 'primitive') return node.raw;
    if (node.kind === 'string') {
      const canonical = pythonString(node.value);
      if (node.raw !== canonical) fail();
      return canonical;
    }
    if (node.kind === 'number') {
      if (!node.integer) {
        const canonical = pythonFloat(node.raw, node.value);
        if (node.raw !== canonical) fail();
        return canonical;
      }
      try {
        const canonical = BigInt(node.raw).toString();
        if (node.raw !== canonical) fail();
        return canonical;
      } catch { return fail(); }
    }
    if (node.kind === 'array') return `[${node.items.map(item => stringify(item)).join(',')}]`;
    const entries = node.entries.filter(([key]) => !(top && key === omit)).sort(([a], [b]) => codePointCompare(a, b));
    return `{${entries.map(([key, rawKey, child]) => {
      const canonicalKey = pythonString(key);
      if (rawKey !== canonicalKey) fail();
      return `${canonicalKey}:${stringify(child)}`;
    }).join(',')}}`;
  };
  const value = materialize(root) as T;
  return { value, pythonCompactJson: options => stringify(root, options?.omitTopLevelKey, true) };
}

export function strictJsonEqual(left: unknown, right: unknown): boolean {
  if (typeof left !== typeof right || (left === null) !== (right === null)) return false;
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right)
    && left.length === right.length && left.every((item, i) => strictJsonEqual(item, right[i]));
  if (left && right && typeof left === 'object' && typeof right === 'object') {
    const a = Object.keys(left), b = Object.keys(right);
    return a.length === b.length && a.every(key => Object.hasOwn(right, key)
      && strictJsonEqual((left as Record<string, unknown>)[key], (right as Record<string, unknown>)[key]));
  }
  return left === right;
}
