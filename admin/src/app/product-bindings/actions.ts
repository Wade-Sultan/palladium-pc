'use server';

import { revalidatePath } from 'next/cache';
import { db } from '@/lib/prisma';
import {
  BindingError,
  bindManuallyTx,
  confirmCandidateTx,
  rejectCandidateTx,
  retireBindingTx,
} from '@/lib/product-binding-transitions';

// Every action returns { error?: string } rather than throwing, like the
// discovery page: thrown server-action messages are masked in production, and
// "that product is already confirmed for this part" has to reach the admin.
// The state changes themselves, and the invariants they keep, live in
// @/lib/product-binding-transitions.

type Result = { error?: string };

async function act(work: () => Promise<void>, fallback: string): Promise<Result> {
  try {
    await work();
  } catch (e) {
    return { error: e instanceof BindingError ? e.message : fallback };
  }
  revalidatePath('/product-bindings');
  return {};
}

export async function confirmCandidate(bindingId: string): Promise<Result> {
  return act(() => confirmCandidateTx(db, bindingId), 'Could not confirm.');
}

export async function rejectCandidate(bindingId: string): Promise<Result> {
  return act(() => rejectCandidateTx(db, bindingId), 'Could not reject.');
}

export async function retireBinding(bindingId: string): Promise<Result> {
  return act(() => retireBindingTx(db, bindingId), 'Could not retire.');
}

export async function bindManually(partId: string, input: string): Promise<Result> {
  return act(() => bindManuallyTx(db, partId, input), 'Could not bind.');
}
