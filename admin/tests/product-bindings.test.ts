import assert from 'node:assert/strict';
import test from 'node:test';
import { googleShoppingUrl, parseGoogleProductId, readEvidence } from '../src/lib/product-bindings';

const ID = '14072215030660324520';

test('a bare catalog id is accepted as is', () => {
  assert.equal(parseGoogleProductId(ID), ID);
  assert.equal(parseGoogleProductId(`  ${ID}\n`), ID);
});

test('every Shopping URL form seen so far yields the id', () => {
  // The google_product_url SerpApi returned for the first real capture.
  assert.equal(
    parseGoogleProductId(
      `https://www.google.com/search?ibp=oshop&q=search&prds=catalogid%3A${ID}&hl=en&gl=us&udm=28`,
    ),
    ID,
  );
  assert.equal(
    parseGoogleProductId(
      `https://www.google.com/search?q=x&prds=catalogid:${ID},headlineOfferDocid:123,imageDocid:456`,
    ),
    ID,
  );
  assert.equal(parseGoogleProductId(`https://www.google.com/shopping/product/${ID}?hl=en`), ID);
  assert.equal(parseGoogleProductId(`https://serpapi.com/search?engine=google_product&product_id=${ID}`), ID);
});

test('anything else is refused rather than guessed', () => {
  assert.equal(parseGoogleProductId(''), null);
  assert.equal(parseGoogleProductId('12345'), null); // too short to be a catalog id
  assert.equal(parseGoogleProductId('https://www.amazon.com/dp/B0BTZB7F88'), null);
  assert.equal(parseGoogleProductId('AMD Ryzen 7 7800X3D'), null);
  assert.equal(parseGoogleProductId('https://www.google.com/search?q=100%broken'), null);
});

test('the review link round-trips through the parser', () => {
  assert.equal(parseGoogleProductId(googleShoppingUrl(ID)), ID);
});

test('evidence is read defensively', () => {
  const e = readEvidence({
    query: 'AMD Ryzen 7 9800X3D processor',
    decision: 'review',
    identity: 'model',
    why_not_auto: ['2 distinct products survived', 42],
    candidate: { coverage: 100, price_cents: 45900, multiple_sources: true, source: 'Newegg.com' },
  });
  assert.equal(e.query, 'AMD Ryzen 7 9800X3D processor');
  assert.deepEqual(e.whyNotAuto, ['2 distinct products survived']);
  assert.equal(e.coverage, 100);
  assert.equal(e.priceCents, 45900);
  assert.equal(e.multipleSources, true);
  assert.equal(e.modelNumberInTitle, false);

  const empty = readEvidence(null);
  assert.equal(empty.query, null);
  assert.deepEqual(empty.whyNotAuto, []);
});
