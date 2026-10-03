/** Crossref supplies bibliographic metadata, never extracted measurement ground truth.
 * Contract: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
 */
import { assertNotAirgapped } from './airgap';

export interface LiteratureSearchItem {
  doi: string;
  title: string;
  authors: string[];
  year: number | null;
  journal: string;
  url: string;
  publicationType: string;
}

export function researchSearchUrl(query: unknown): URL {
  assertNotAirgapped('Crossref literature search');
  if (typeof query !== 'string' || query.trim().length < 3 || query.length > 500) {
    throw new Error('Enter a research query or DOI between 3 and 500 characters.');
  }
  const cleaned = query.trim().replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').replace(/^doi:\s*/i, '');
  const doi = /^10\.\d{4,9}\/\S+$/i.test(cleaned);
  const url = new URL(doi ? `https://api.crossref.org/works/${encodeURIComponent(cleaned)}` : 'https://api.crossref.org/works');
  if (!doi) {
    url.searchParams.set('query.bibliographic', query.trim());
    url.searchParams.set('rows', '12');
    url.searchParams.set('select', 'DOI,title,author,published,container-title,type');
  }
  return url;
}

export function normalizeCrossrefResponse(payload: unknown): LiteratureSearchItem[] {
  const envelope = payload as { message?: { items?: unknown[]; DOI?: unknown } } | null;
  if (!envelope?.message || typeof envelope.message !== 'object') throw new Error('Literature provider returned an invalid response.');
  const rows = Array.isArray(envelope.message.items) ? envelope.message.items : envelope.message.DOI ? [envelope.message] : null;
  if (!rows) throw new Error('Literature provider returned no recognizable records.');
  return rows.slice(0, 12).flatMap((raw: any) => {
    if (typeof raw?.DOI !== 'string' || !/^10\.\d{4,9}\/\S+$/i.test(raw.DOI) || !Array.isArray(raw.title) || typeof raw.title[0] !== 'string') return [];
    const year = raw.published?.['date-parts']?.[0]?.[0];
    return [{
      doi: raw.DOI,
      title: raw.title[0].replace(/<[^>]*>/g, '').slice(0, 2000),
      authors: Array.isArray(raw.author) ? raw.author.slice(0, 30).map((a: any) => [a.given, a.family].filter(v => typeof v === 'string').join(' ')) : [],
      year: Number.isInteger(year) && year > 1000 && year < 3000 ? year : null,
      journal: Array.isArray(raw['container-title']) && typeof raw['container-title'][0] === 'string' ? raw['container-title'][0] : '',
      url: `https://doi.org/${encodeURI(raw.DOI)}`,
      publicationType: typeof raw.type === 'string' ? raw.type : 'unknown',
    }];
  });
}
