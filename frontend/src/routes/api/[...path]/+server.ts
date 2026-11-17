import { CORE_API_URL } from '$app/env/private';
import { MAX_SAVE_BYTES } from '#lib/save-limit.ts';
import type { RequestHandler } from './$types';

const proxy: RequestHandler = async ({ request, params, url }) => {
  const path = params.path.split('/').map(encodeURIComponent).join('/');
  const target = new URL(`/api/${path}${url.search}`, CORE_API_URL);
  const headers = new Headers();
  for (const key of ['content-type', 'cookie', 'accept']) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const saveUpload = request.method === 'POST' && /^games\/import(?:\/preview)?$/.test(path);
  try {
    let body: Uint8Array<ArrayBuffer> | ArrayBuffer | undefined;
    if (saveUpload && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_SAVE_BYTES) {
          void reader.cancel().catch(() => {});
          return Response.json({ detail: 'The save file is larger than 8 MB.' }, {
            status: 413,
            headers: { 'x-game-error-code': 'save_file_too_large' }
          });
        }
        chunks.push(value);
      }
      body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        body.set(chunk, offset);
        offset += chunk.byteLength;
      }
    } else if (request.body) {
      body = await request.arrayBuffer();
    }
    const upstream = await fetch(target, {
      method: request.method,
      body,
      headers,
      redirect: 'manual',
      signal: AbortSignal.timeout(15_000)
    });
    const result = new Headers({ 'Cache-Control': 'no-store' });
    for (const key of ['content-type', 'content-disposition', 'x-content-type-options', 'x-game-error-code', 'x-game-error-values']) {
      const value = upstream.headers.get(key);
      if (value) result.set(key, value);
    }
    for (const cookie of upstream.headers.getSetCookie()) result.append('set-cookie', cookie);
    return new Response(upstream.body, { status: upstream.status, headers: result });
  } catch {
    return Response.json({ detail: 'The game server is unavailable. Try again shortly.' }, {
      status: 503,
      headers: { 'x-game-error-code': 'upstream_unavailable' }
    });
  }
};

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
