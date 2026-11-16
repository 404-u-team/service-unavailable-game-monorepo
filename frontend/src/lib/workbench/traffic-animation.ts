import type { Speed } from '../types';

type Packet = { id: number; distance: number };
export type Traffic = { packets: Packet[]; emission: number; nextId: number };

const travelPerSecond = 42;
const maxPackets = 12;
const maxFrequency = 3.75;

export function advanceTraffic(traffic: Traffic, length: number, rate: number, speed: Speed, seconds: number) {
  const travel = travelPerSecond * speed * seconds;
  if (!travel) return traffic.packets;

  const packets = traffic.packets.flatMap(({ id, distance }) => {
    const next = distance + travel;
    return next < length ? [{ id, distance: next }] : [];
  });

  if (rate > 0) {
    // Map the measured rate to readable spacing while keeping circles separate at high load.
    const frequency = .55 + (maxFrequency - .55) * rate / (rate + 180);
    const spacing = Math.max(travelPerSecond, length * maxFrequency / maxPackets) / frequency;
    traffic.emission += travel / spacing;
    const count = Math.floor(traffic.emission);
    traffic.emission -= count;
    for (let i = Math.min(count, maxPackets) - 1; i >= 0; i--) {
      const distance = (traffic.emission + i) * spacing;
      if (distance < length) packets.push({ id: traffic.nextId++, distance });
    }
  }

  traffic.packets = packets;
  return packets;
}

const listeners = new Set<(seconds: number) => void>();
let frame: number | undefined;
let previousTime: number | undefined;

function tick(time: number) {
  const seconds = previousTime === undefined ? 0 : (time - previousTime) / 1000;
  previousTime = time;
  for (const listener of listeners) listener(seconds);
  frame = requestAnimationFrame(tick);
}

export function onTrafficFrame(listener: (seconds: number) => void) {
  if (!listeners.size) frame = requestAnimationFrame(tick);
  listeners.add(listener);

  return () => {
    listeners.delete(listener);
    if (!listeners.size && frame !== undefined) {
      cancelAnimationFrame(frame);
      frame = previousTime = undefined;
    }
  };
}
