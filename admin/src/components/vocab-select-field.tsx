'use client';

import type { Control, FieldPath, FieldValues } from 'react-hook-form';
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

/** A form field restricted to a fixed vocabulary. A stored value outside the
 * list shows as unselected, so saving forces a valid choice. */
export function VocabSelectField<T extends FieldValues>({ control, name, label, options }: {
  control: Control<T>;
  name: FieldPath<T>;
  label: string;
  options: readonly { value: string; label: string }[];
}) {
  return (
    <FormField control={control} name={name} render={({ field }) => (
      <FormItem>
        <FormLabel>{label}</FormLabel>
        <Select
          value={options.some((o) => o.value === field.value) ? field.value : ''}
          onValueChange={field.onChange}
        >
          <FormControl><SelectTrigger><SelectValue placeholder="Choose..." /></SelectTrigger></FormControl>
          <SelectContent>
            {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <FormMessage />
      </FormItem>
    )} />
  );
}
