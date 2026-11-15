import type { Tone } from './types';

export type ToastMessage = {
  title: string;
  description?: string;
  tone?: Tone;
  duration?: number;
  announce?: 'polite' | 'assertive';
};

export type ToastItem = Readonly<ToastMessage & { id: number }>;

export function createToasts() {
  let items = $state.raw<readonly ToastItem[]>([]);
  let nextId = 0;

  return {
    get items() { return items; },
    add(message: ToastMessage) {
      const id = ++nextId;
      items = [...items, { ...message, id }];
      return id;
    },
    dismiss(id: number) { items = items.filter((item) => item.id !== id); },
    clear() { items = []; }
  };
}

export type Toasts = ReturnType<typeof createToasts>;
