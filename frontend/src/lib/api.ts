import { difficulties, type Catalog, type Game, type Save } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public values: string[] = []) {
    super(message);
  }
}

export async function api<T>(path: string, method = 'GET', data?: object): Promise<T> {
  const response = await fetch(`/api/games${path}`, {
    method,
    headers: data ? { 'Content-Type': 'application/json' } : undefined,
    body: data ? JSON.stringify(data) : undefined,
    cache: 'no-store'
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const message = Array.isArray(result?.detail)
      ? 'Some submitted values are invalid.'
      : result?.detail;
    const code = response.headers.get('x-game-error-code') ??
      (response.status === 422 && Array.isArray(result?.detail) ? 'invalid_values' : undefined);
    const values = JSON.parse(response.headers.get('x-game-error-values') ?? '[]') as string[];
    throw new ApiError(response.status, typeof message === 'string' ? message : 'The request could not be completed.', code, values);
  }
  return result as T;
}

export const saves = () => api<Save[]>('');

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export async function loadCatalog(): Promise<Catalog> {
  const catalog = await api<unknown>('/catalog');
  const profiles = isRecord(catalog) ? catalog.difficulties : undefined;
  if (!isRecord(catalog) || catalog.diagram_layout !== true ||
      !['components', 'scenarios', 'features', 'campaigns', 'operations', 'connections'].every((key) => isRecord(catalog[key])) ||
      typeof catalog.minutes_per_tick !== 'number' || !isRecord(profiles) ||
      difficulties.some((key) => {
        const option = profiles[key];
        return !isRecord(option) || typeof option.name !== 'string' ||
          typeof option.balance !== 'number' || typeof option.audience !== 'number';
      })) {
    throw new ApiError(502, 'The game server returned an incompatible catalog. Check the API address and rebuild the API container, then retry.', 'incompatible_catalog');
  }
  return catalog as Catalog;
}
export const loadGame = (id: string) => api<Game>(`/${id}`);
export const createGame = (body: object) => api<Game>('', 'POST', body);
export const gameAction = (id: string, path: string, body: object = {}, method = 'POST', requestId: string = crypto.randomUUID()) =>
  api<Game>(`/${id}${path}`, method, { ...body, request_id: requestId });
