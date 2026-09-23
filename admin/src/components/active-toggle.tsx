'use client';

import { useOptimistic, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { Checkbox } from '@/components/ui/checkbox';
import { setPartActive } from '@/lib/part-active';

export function ActiveToggle({ partId, active, page }: { partId: string; active: boolean; page: string }) {
  const router = useRouter();
  const [shown, setShown] = useOptimistic(active);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  return (
    <div className="flex items-center gap-2">
      <Checkbox
        checked={shown}
        disabled={pending}
        aria-label={shown ? 'Active: uncheck to deactivate' : 'Inactive: check to activate'}
        onCheckedChange={(checked) => startTransition(async () => {
          setShown(checked === true);
          const result = await setPartActive(partId, checked === true, page);
          setError(result.error ?? null);
          router.refresh();
        })}
      />
      {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
    </div>
  );
}
