import type { Game } from './types';

type WindowPatch<T> = { drop: number; append: T[] };
type GamePatch = Omit<Partial<Game>, 'economy'> & { economy?: Partial<Game['economy']> };
type Frame = { type: 'snapshot'; seq: number; state: Game } | {
  type: 'patch'; seq: number; changes: GamePatch;
  histories: {
    history?: WindowPatch<Game['history'][number]>;
    business_history?: WindowPatch<Game['business_history'][number]>;
    finance?: WindowPatch<Game['economy']['history'][number]>;
  };
};

function applyWindow<T>(values: T[], patch?: WindowPatch<T>): T[] {
  return patch ? values.slice(patch.drop).concat(patch.append) : values;
}

export function applyFrame(current: { seq: number; state: Game } | undefined, frame: Frame) {
  if (current && frame.seq <= current.seq) return current;
  if (frame.type === 'snapshot') return { seq: frame.seq, state: frame.state };
  if (!current || frame.seq !== current.seq + 1) throw new Error('Game update sequence is incomplete.');
  const { state } = current;
  return {
    seq: frame.seq,
    state: {
      ...state, ...frame.changes,
      history: applyWindow(state.history, frame.histories.history),
      business_history: applyWindow(state.business_history, frame.histories.business_history),
      economy: { ...state.economy, ...frame.changes.economy, history: applyWindow(state.economy.history, frame.histories.finance) }
    }
  };
}

export function subscribeGame(id: string, accept: (state: Game) => void, status: (connected: boolean) => void) {
  let socket: WebSocket | undefined;
  let retry: ReturnType<typeof setTimeout>;
  let watchdog: ReturnType<typeof setTimeout>;
  let failures = 0;
  let stopped = false;

  function connect() {
    clearTimeout(retry);
    clearTimeout(watchdog);
    const url = new URL(`/api/games/${encodeURIComponent(id)}/live`, window.location.href);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const connection = new WebSocket(url);
    socket = connection;
    let current: ReturnType<typeof applyFrame> | undefined;
    const resetWatchdog = () => {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => connection.close(), 25_000);
    };
    resetWatchdog();
    connection.onmessage = (event) => {
      if (socket !== connection || stopped) return;
      resetWatchdog();
      try {
        const frame = JSON.parse(event.data);
        if (frame.type === 'heartbeat' && current) return;
        if (frame.type !== 'snapshot' && frame.type !== 'patch') throw new Error('Unknown game update.');
        const next = applyFrame(current, frame);
        if (current === next) return;
        if (next.state.id !== id) throw new Error('Wrong game subscription.');
        if (!current) {
          failures = 0;
          status(true);
        }
        current = next;
        accept(next.state);
      } catch {
        connection.close();
      }
    };
    connection.onclose = () => {
      if (socket !== connection || stopped) return;
      clearTimeout(watchdog);
      status(false);
      retry = setTimeout(connect, Math.min(15_000, 500 * 2 ** failures++) + Math.random() * 250);
    };
  }
  connect();

  return {
    reconnect() {
      const previous = socket;
      connect();
      previous?.close();
    },
    close() {
      stopped = true;
      clearTimeout(retry);
      clearTimeout(watchdog);
      socket?.close();
    }
  };
}
