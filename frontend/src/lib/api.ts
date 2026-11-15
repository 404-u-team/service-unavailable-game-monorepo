import { MAX_SAVE_BYTES } from './save-limit';
import { difficulties, type Catalog, type Game, type Save, type SavePreview } from './types';

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
  if (!response.ok) await throwApiError(response);
  return await response.json() as T;
}

async function throwApiError(response: Response): Promise<never> {
  const result = await response.json().catch(() => null);
  const message = Array.isArray(result?.detail)
    ? 'Some submitted values are invalid.'
    : result?.detail;
  const code = response.headers.get('x-game-error-code') ??
    (response.status === 413 ? 'save_file_too_large' :
      response.status === 422 && Array.isArray(result?.detail) ? 'invalid_values' : undefined);
  const values = JSON.parse(response.headers.get('x-game-error-values') ?? '[]') as string[];
  throw new ApiError(response.status, typeof message === 'string' ? message : 'The request could not be completed.', code, values);
}

export const saves = () => api<Save[]>('');

async function uploadSave<T>(file: File, preview: boolean): Promise<T> {
  if (file.size > MAX_SAVE_BYTES) throw new ApiError(413, '', 'save_file_too_large');
  const response = await fetch(`/api/games/import${preview ? '/preview' : ''}`, {
    method: 'POST', body: file, headers: { 'Content-Type': 'application/json' }
  });
  if (!response.ok) await throwApiError(response);
  return response.json();
}

export const previewSave = (file: File) => uploadSave<SavePreview>(file, true);
export const importSave = (file: File) => uploadSave<Save>(file, false);

export async function downloadSave(id: string): Promise<void> {
  const response = await fetch(`/api/games/${id}/export`, { cache: 'no-store' });
  if (!response.ok) await throwApiError(response);
  const filename = response.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = filename ?? 'service-unavailable-save.json';
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export async function loadCatalog(): Promise<Catalog> {
  const catalog = await api<unknown>('/catalog');
  const profiles = isRecord(catalog) ? catalog.difficulties : undefined;
  if (!isRecord(catalog) || catalog.diagram_layout !== true ||
      !['components', 'scenarios', 'features', 'campaigns', 'operations', 'connections', 'engineering', 'service_roles', 'operation_domains'].every((key) => isRecord(catalog[key])) ||
      typeof catalog.days_per_month !== 'number' || typeof catalog.minutes_per_tick !== 'number' || !isRecord(profiles) ||
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
