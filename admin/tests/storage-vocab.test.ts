import assert from 'node:assert/strict';
import test from 'node:test';
import { storageVocabError } from '../src/lib/storage-vocab';

test('storage groups accept only the vocabulary the recommender reads', () => {
  assert.equal(storageVocabError({ storageType: 'ssd', formFactor: '2.5', interface: 'sata3' }), null);
  assert.equal(storageVocabError({ storageType: 'nvme', formFactor: 'm2_2280', interface: 'pcie_gen4' }), null);
  // The hand-entered spellings that hid SATA drives from the recommender.
  assert.match(storageVocabError({ storageType: 'sata_ssd', formFactor: '2.5', interface: 'sata3' })!, /type/);
  assert.match(storageVocabError({ storageType: 'ssd', formFactor: '2_5_inch', interface: 'sata3' })!, /form factor/);
  assert.match(storageVocabError({ storageType: 'ssd', formFactor: '2.5', interface: 'sata' })!, /interface/);
  assert.match(storageVocabError({ storageType: 'nvme', formFactor: 'm2_2280', interface: 'sata3' })!, /not SATA/);
  assert.match(storageVocabError({ storageType: 'hdd', formFactor: '3.5', interface: 'pcie_gen4' })!, /not PCIe/);
});
