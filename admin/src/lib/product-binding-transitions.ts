// State changes on google_product_bindings, separate from the server actions so
// they can be driven against a real database without Next.js (see
// scripts/mk-verify-product-bindings.sh). The actions wrap these with
// revalidatePath and turn thrown errors into { error }.
//
// THE INVARIANTS, matching the backend (app/models/price_tracking.py):
//   - google_product_id is never edited. A different product is a new row.
//   - At most one 'confirmed' row per part. A partial unique index enforces it,
//     and it is checked per statement, so every path RETIRES the old confirmed
//     row BEFORE confirming the new one.
//   - Rows are never deleted. Rejected and retired rows record what was ruled
//     out, and discovery reads them so it never re-proposes one.

import type { PrismaClient, Prisma } from '@prisma/client';
import { parseGoogleProductId } from './product-bindings';

type Tx = Prisma.TransactionClient;

export class BindingError extends Error {}

async function retireConfirmed(tx: Tx, partId: string, now: Date) {
  await tx.googleProductBinding.updateMany({
    where: { partId, status: 'confirmed' },
    data: { status: 'retired', statusChangedAt: now },
  });
}

async function rejectOtherCandidates(tx: Tx, partId: string, keepId: string, now: Date) {
  await tx.googleProductBinding.updateMany({
    where: { partId, status: 'candidate', NOT: { id: keepId } },
    data: { status: 'rejected', statusChangedAt: now },
  });
}

/** Accept a candidate as THE product for its part. The part's other pending
 * candidates are rejected: once one is right, the others are not. */
export async function confirmCandidateTx(db: PrismaClient, bindingId: string) {
  await db.$transaction(async (tx) => {
    const row = await tx.googleProductBinding.findUnique({ where: { id: bindingId } });
    if (!row) throw new BindingError('That candidate no longer exists.');
    if (row.status !== 'candidate') throw new BindingError(`It is already ${row.status}.`);
    const now = new Date();
    await retireConfirmed(tx, row.partId, now);
    await tx.googleProductBinding.update({
      where: { id: row.id },
      data: { status: 'confirmed', confirmedBy: 'admin', statusChangedAt: now },
    });
    await rejectOtherCandidates(tx, row.partId, row.id, now);
  });
}

export async function rejectCandidateTx(db: PrismaClient, bindingId: string) {
  const updated = await db.googleProductBinding.updateMany({
    where: { id: bindingId, status: 'candidate' },
    data: { status: 'rejected', statusChangedAt: new Date() },
  });
  if (updated.count === 0) throw new BindingError('That candidate was already reviewed.');
}

/** Stop pricing a part through this product. The part goes back to needing a
 * binding, and discovery will not propose this id again. */
export async function retireBindingTx(db: PrismaClient, bindingId: string) {
  const updated = await db.googleProductBinding.updateMany({
    where: { id: bindingId, status: { in: ['confirmed', 'stale'] } },
    data: { status: 'retired', statusChangedAt: new Date() },
  });
  if (updated.count === 0) throw new BindingError('That binding is not active.');
}

/** Bind a part to a product id (or Shopping URL) an admin found themselves:
 * the way out for parts discovery cannot find, like the 9800X3D. */
export async function bindManuallyTx(db: PrismaClient, partId: string, input: string) {
  const productId = parseGoogleProductId(input);
  if (!productId) {
    throw new BindingError(
      'Paste a Google Shopping product URL (one containing "catalogid:") or the numeric product id.',
    );
  }
  await db.$transaction(async (tx) => {
    const part = await tx.pcPart.findUnique({ where: { id: partId }, select: { id: true } });
    if (!part) throw new BindingError('That part no longer exists.');
    const existing = await tx.googleProductBinding.findUnique({
      where: { partId_googleProductId: { partId, googleProductId: productId } },
    });
    if (existing?.status === 'confirmed') {
      throw new BindingError('That product is already confirmed for this part.');
    }
    const now = new Date();
    await retireConfirmed(tx, partId, now);
    const row = existing
      ? await tx.googleProductBinding.update({
          where: { id: existing.id },
          data: { status: 'confirmed', confirmedBy: 'admin', statusChangedAt: now },
        })
      : await tx.googleProductBinding.create({
          data: {
            partId,
            googleProductId: productId,
            status: 'confirmed',
            confirmedBy: 'admin',
            matchEvidence: { source: 'admin', input: input.trim().slice(0, 2000) },
            statusChangedAt: now,
          },
        });
    await rejectOtherCandidates(tx, partId, row.id, now);
  });
}
