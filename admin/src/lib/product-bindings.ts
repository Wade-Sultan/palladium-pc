// Turning what an admin pastes into a Google Shopping product id.
//
// The id is Google's catalog id: the digits after "catalogid:" in a Shopping
// URL, and the `product_id` SerpApi's google_product engine accepts. Admins will
// paste whatever their browser shows, so every form seen so far is accepted:
//
//   14072215030660324520
//   https://www.google.com/search?ibp=oshop&q=search&prds=catalogid%3A14072215030660324520&udm=28
//   https://www.google.com/search?...prds=catalogid:14072215030660324520,headlineOfferDocid:...
//   https://www.google.com/shopping/product/14072215030660324520
//
// Anything else is refused rather than guessed: a wrong id binds a part to some
// other product's price series.

const ID = /^\d{6,25}$/;

export function parseGoogleProductId(input: string): string | null {
  const text = input.trim();
  if (!text) return null;
  if (ID.test(text)) return text;

  let decoded = text;
  try {
    decoded = decodeURIComponent(text);
  } catch {
    // A stray % in a pasted string; the raw text is still worth a look.
  }

  const catalog = decoded.match(/catalogid:(\d{6,25})\b/i);
  if (catalog) return catalog[1];

  const path = decoded.match(/\/shopping\/product\/(\d{6,25})\b/i);
  if (path) return path[1];

  const param = decoded.match(/[?&]product_id=(\d{6,25})\b/i);
  if (param) return param[1];

  return null;
}

/** Where an admin can look at the product Google means by this id. */
export function googleShoppingUrl(productId: string): string {
  return `https://www.google.com/search?ibp=oshop&q=search&prds=catalogid%3A${encodeURIComponent(productId)}&udm=28`;
}

/** The fields of match_evidence the review page shows, read defensively: it
 * is JSONB written by the backend and may predate a field. */
export interface CandidateEvidence {
  query: string | null;
  decision: string | null;
  identity: string | null;
  whyNotAuto: string[];
  coverage: number | null;
  similarity: number | null;
  priceCents: number | null;
  priceRatio: number | null;
  source: string | null;
  multipleSources: boolean;
  modelNumberInTitle: boolean;
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v ? v : null;
}

export function readEvidence(raw: unknown): CandidateEvidence {
  const e = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const c = (e.candidate && typeof e.candidate === 'object' ? e.candidate : {}) as Record<
    string,
    unknown
  >;
  return {
    query: str(e.query),
    decision: str(e.decision),
    identity: str(e.identity),
    whyNotAuto: Array.isArray(e.why_not_auto) ? e.why_not_auto.filter((x) => typeof x === 'string') : [],
    coverage: num(c.coverage),
    similarity: num(c.similarity),
    priceCents: num(c.price_cents),
    priceRatio: num(c.price_ratio),
    source: str(c.source),
    multipleSources: c.multiple_sources === true,
    modelNumberInTitle: c.model_number_in_title === true,
  };
}
