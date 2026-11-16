import { expect, test } from 'bun:test';
import { advanceTraffic, type Traffic } from '../src/lib/workbench/traffic-animation';
import type { Speed } from '../src/lib/types';

function traffic(): Traffic {
  return { packets: [], emission: 1, nextId: 0 };
}

test('tempo changes preserve in-flight packets and multiply their travel by the simulation speed', () => {
  const flow = traffic();
  const [initial] = advanceTraffic(flow, 120, 100, 1, .1);
  const [normal] = advanceTraffic(flow, 120, 150, 1, .1);
  const [fast] = advanceTraffic(flow, 120, 350, 5, .1);
  expect(fast.id).toBe(initial.id);
  expect(fast.distance - normal.distance).toBeCloseTo(5 * (normal.distance - initial.distance));
  expect(advanceTraffic(flow, 120, 25, 0, .1)[0]).toEqual(fast);
  expect(advanceTraffic(flow, 120, 0, 1, .1)[0].distance).toBeGreaterThan(fast.distance);
});

test('higher measured rates emit more packets and faster speeds compress the same traffic in time', () => {
  function replay(rate: number, speed: Speed, frames: number) {
    const flow = traffic();
    for (let frame = 0; frame < frames; frame++) advanceTraffic(flow, 150, rate, speed, .05);
    return flow;
  }

  const light = replay(10, 1, 50);
  const heavy = replay(1_000, 1, 50);
  const fast = replay(1_000, 5, 10);
  expect(heavy.packets.length).toBeGreaterThan(light.packets.length);
  expect(fast.packets).toHaveLength(heavy.packets.length);
  for (const [index, packet] of fast.packets.entries()) {
    expect(packet.distance).toBeCloseTo(heavy.packets[index].distance);
  }
});
