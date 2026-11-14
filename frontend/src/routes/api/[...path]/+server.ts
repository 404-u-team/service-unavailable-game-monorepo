import { CORE_API_URL } from '$app/env/private';
import type { RequestHandler } from './$types';

const proxy: RequestHandler = async ({ request, params, url }) => {
  const path = params.path.split('/').map(encodeURIComponent).join('/');
  const target = new URL(`/api/${path}${url.search}`, CORE_API_URL);
  const headers = new Headers();
  for (const key of ['content-type', 'cookie', 'accept']) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      body: request.method === 'GET' ? undefined : await request.arrayBuffer(),
      headers,
      redirect: 'manual',
      signal: AbortSignal.timeout(15_000)
    });
    const result = new Headers({ 'Cache-Control': 'no-store' });
    for (const key of ['content-type', 'x-game-error-code', 'x-game-error-values']) {
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
