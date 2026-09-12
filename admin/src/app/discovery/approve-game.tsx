'use client';

import { useState, useTransition } from 'react';
import { Button } from '@/components/ui/button';
import { asRecord } from '@/lib/discovery-review';
import { approveGame } from './actions';

export function ApproveGameForm({ itemId, extractedFields, onSuccess }: {
  itemId: string; extractedFields: Record<string, unknown>; onSuccess: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const requirements = Array.isArray(extractedFields.requirements) ? extractedFields.requirements : [];
  return <div className="space-y-4">
    <p>Approve the missing CPUs and GPU chipsets in the discovery queue first. CPUs added for these requirements stay inactive until you activate them separately.</p>
    <ul className="space-y-2">
      {requirements.map((value, index) => {
        const req = asRecord(value);
        return <li key={index} className="rounded border p-3">
          <strong>{String(req.tier)} · {String(req.role).toUpperCase()}</strong>: {String(req.published_name)}
        </li>;
      })}
    </ul>
    {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    <Button disabled={pending} onClick={() => startTransition(async () => {
      setError(null);
      const result = await approveGame(itemId);
      if (result.error) setError(result.error);
      else onSuccess();
    })}>{pending ? 'Approving…' : 'Approve game and link requirements'}</Button>
  </div>;
}
