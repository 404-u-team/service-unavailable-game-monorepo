import { ApiError, gameAction } from '../api';
import type { Diagram, Game } from '../types';
import { diagramPatch, mergeLayout } from './diagram';

type Edit = { base: Diagram; next: Diagram; requestId?: string };
const draftKey = (id: string) => `workbench-unsaved-layout:${id}`;

export function syncLayout(id: string, display: (diagram?: Diagram) => void,
  accept: (game: Game) => void, failed: (value: boolean) => void) {
  let pending: Edit | undefined;
  let sending: Edit | undefined;
  let active: Promise<boolean> | undefined;
  let timer: ReturnType<typeof setTimeout>;
  let retryDelay = 0;
  let stopped = false;

  try {
    const cached = sessionStorage.getItem(draftKey(id));
    if (cached) pending = JSON.parse(cached);
  } catch { /* Storage can be unavailable in private or restricted browsing. */ }

  function schedule(delay = 700) {
    clearTimeout(timer);
    if (!stopped && pending) timer = setTimeout(() => void flush(), delay);
  }

  function remember() {
    const edit = pending && sending ? { base: sending.base, next: pending.next } : pending ?? sending;
    try {
      if (edit) sessionStorage.setItem(draftKey(id), JSON.stringify(edit));
      else sessionStorage.removeItem(draftKey(id));
    } catch { /* The in-memory edit is still available. */ }
    if (!stopped) display(edit?.next);
  }

  async function send(): Promise<boolean> {
    while (pending) {
      const edit = pending;
      const patch = diagramPatch(edit.base, edit.next);
      pending = undefined;
      edit.requestId ??= crypto.randomUUID();
      sending = edit;
      try {
        if (patch) {
          const state = await gameAction(id, '/diagram', patch, 'PATCH', edit.requestId);
          if (!stopped) accept(state);
        }
        retryDelay = 0;
        if (!stopped) failed(false);
      } catch (error) {
        const later = pending as Edit | undefined;
        pending = later ? { base: edit.base, next: later.next } : edit;
        if (!stopped) failed(true);
        if (!(error instanceof ApiError) || error.status >= 500) {
          retryDelay = Math.min(8000, retryDelay ? retryDelay * 2 : 1000);
          schedule(retryDelay);
        }
        return false;
      } finally {
        sending = undefined;
        remember();
      }
    }
    return true;
  }

  function flush() {
    clearTimeout(timer);
    active ??= send().finally(() => { active = undefined; });
    return active;
  }

  remember();
  schedule();
  return {
    queue(base: Diagram, next: Diagram) {
      pending = { base: pending?.base ?? base, next };
      remember();
      schedule();
    },
    flush,
    async retry(latest: Diagram) {
      if (pending) pending = { base: latest, next: mergeLayout(latest, pending.base, pending.next) };
      remember();
      return flush();
    },
    close() {
      stopped = true;
      void flush();
    }
  };
}
