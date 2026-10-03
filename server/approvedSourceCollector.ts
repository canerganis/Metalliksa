import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertNotAirgapped } from "./airgap";

const MAX_BYTES = 25 * 1024 * 1024;
const REQUEST_TIMEOUT_MS = 30_000;

export const APPROVED_SOURCE_HOSTS = {
  nistAmbench: ["nist.gov", "www.nist.gov"],
  materialsProject: ["materialsproject.org", "api.materialsproject.org"],
  nomad: ["nomad-laboratory.eu", "nomad-coe.eu"],
} as const;

export type ApprovedSourceId = keyof typeof APPROVED_SOURCE_HOSTS;

function isApprovedHost(hostname: string, hosts: readonly string[]) {
  return hosts.some((host) => hostname === host || hostname.endsWith(`.${host}`));
}

function safeFileName(value: string) {
  return value.replace(/[^a-z0-9._-]+/gi, "-").replace(/^-+|-+$/g, "").slice(0, 120) || "source";
}

export async function collectApprovedSource(sourceId: ApprovedSourceId, rawUrl: string) {
  assertNotAirgapped("Approved external source download");
  const url = new URL(rawUrl);
  if (url.protocol !== "https:") throw new Error("Only HTTPS source URLs are allowed.");
  if (!isApprovedHost(url.hostname, APPROVED_SOURCE_HOSTS[sourceId])) {
    throw new Error(`The URL is not allowed for approved source '${sourceId}'.`);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url, { signal: controller.signal, redirect: "error", headers: { "User-Agent": "Metalliksa-approved-source-collector/1.0" } });
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) throw new Error(`Source responded with HTTP ${response.status}.`);

  const contentLength = Number(response.headers.get("content-length") || 0);
  if (contentLength > MAX_BYTES) throw new Error("Source file exceeds the 25 MB safety limit.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > MAX_BYTES) throw new Error("Source file exceeds the 25 MB safety limit.");

  const hash = createHash("sha256").update(bytes).digest("hex");
  const extension = path.extname(url.pathname).slice(0, 12) || ".bin";
  const root = path.resolve(process.cwd(), "data", "collected-sources");
  const fileName = `${sourceId}-${hash.slice(0, 16)}${safeFileName(extension)}`;
  await mkdir(root, { recursive: true });
  const filePath = path.join(root, fileName);
  await writeFile(filePath, bytes, { flag: "wx" });

  const metadata = {
    sourceId,
    sourceUrl: url.toString(),
    downloadedAt: new Date().toISOString(),
    bytes: bytes.byteLength,
    sha256: hash,
    contentType: response.headers.get("content-type") || "application/octet-stream",
    filePath,
    status: "raw" as const,
  };
  await writeFile(`${filePath}.metadata.json`, JSON.stringify(metadata, null, 2), { flag: "wx" });
  return metadata;
}
