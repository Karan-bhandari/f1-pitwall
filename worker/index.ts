export interface Env {
  ASSETS: Fetcher;
  BACKEND_ORIGIN?: string;
  PITWALL_ORIGIN_SECRET?: string;
}

const SUBPATH = "/f1-pitwall";
const API_PREFIX = `${SUBPATH}/api`;

function parseEdgeTtl(headerVal: string | null): number {
  if (!headerVal) return 0;
  const sMax = headerVal.match(/(?:^|[,\s])s-maxage=(\d+)/i);
  if (sMax) return Number(sMax[1]);
  const max = headerVal.match(/(?:^|[,\s])max-age=(\d+)/i);
  return max ? Number(max[1]) : 0;
}

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);

    // Canonical trailing slash so SPA routes and assets resolve under /f1-pitwall/
    if (url.pathname === SUBPATH) {
      return Response.redirect(`${url.origin}${SUBPATH}/${url.search}`, 301);
    }

    // Edge-cached API gateway: /f1-pitwall/api and /f1-pitwall/api/* -> /api/*
    if (
      url.pathname === API_PREFIX ||
      url.pathname.startsWith(`${API_PREFIX}/`)
    ) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return Response.json({ error: "Method not allowed" }, { status: 405 });
      }

      const isGet = request.method === "GET";
      const edgeCache =
        typeof caches !== "undefined" ? caches.default : undefined;
      const cacheKey = new Request(url.toString(), { method: "GET" });

      if (isGet && edgeCache) {
        try {
          const cached = await edgeCache.match(cacheKey);
          if (cached) {
            const hit = new Response(cached.body, cached);
            hit.headers.set("X-Pitwall-Edge-Cache", "HIT");
            return hit;
          }
        } catch {
          // Local/unsupported cache environment: fall through to origin
        }
      }

      const isLocal =
        url.hostname === "localhost" ||
        url.hostname === "127.0.0.1" ||
        url.hostname === "[::1]";
      const origin = (
        env.BACKEND_ORIGIN || (isLocal ? "http://127.0.0.1:5005" : "")
      )
        .trim()
        .replace(/\/$/, "");

      if (!origin) {
        return Response.json(
          { error: "Backend origin is not configured." },
          { status: 502 },
        );
      }

      const upstreamPath = url.pathname.slice(SUBPATH.length);
      const upstreamUrl = `${origin}${upstreamPath}${url.search}`;

      const upstreamHeaders = new Headers();
      const accept = request.headers.get("Accept");
      if (accept) upstreamHeaders.set("Accept", accept);
      if (env.PITWALL_ORIGIN_SECRET) {
        upstreamHeaders.set(
          "X-Pitwall-Origin-Secret",
          env.PITWALL_ORIGIN_SECRET,
        );
      }

      let upstreamResp: Response;
      try {
        upstreamResp = await fetch(upstreamUrl, {
          method: request.method,
          headers: upstreamHeaders,
          redirect: "manual",
        });
      } catch {
        return Response.json(
          { error: "Upstream API origin unreachable." },
          { status: 502 },
        );
      }

      if (upstreamResp.status >= 300 && upstreamResp.status < 400) {
        return Response.json(
          { error: "Upstream origin rejected secret or redirected." },
          { status: 502 },
        );
      }

      const respHeaders = new Headers(upstreamResp.headers);
      respHeaders.delete("Set-Cookie");

      // Prefer CDN-Cache-Control because Vercel strips s-maxage from Cache-Control
      const cdnCacheControl = upstreamResp.headers.get("CDN-Cache-Control");
      const cacheControl = upstreamResp.headers.get("Cache-Control");
      const ttl = parseEdgeTtl(cdnCacheControl || cacheControl);

      if (isGet && upstreamResp.status === 200 && ttl > 0 && edgeCache) {
        const bodyForCache = upstreamResp.clone().body;
        const toCacheHeaders = new Headers(respHeaders);
        toCacheHeaders.set("Cache-Control", `public, s-maxage=${ttl}`);
        toCacheHeaders.set("X-Pitwall-Edge-Cache", "HIT");
        ctx.waitUntil(
          edgeCache
            .put(
              cacheKey,
              new Response(bodyForCache, {
                status: upstreamResp.status,
                statusText: upstreamResp.statusText,
                headers: toCacheHeaders,
              }),
            )
            .catch(() => {}),
        );
      }

      if (cdnCacheControl) {
        respHeaders.set("Cache-Control", cdnCacheControl);
      }
      respHeaders.set("X-Pitwall-Edge-Cache", "MISS");

      return new Response(upstreamResp.body, {
        status: upstreamResp.status,
        statusText: upstreamResp.statusText,
        headers: respHeaders,
      });
    }

    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
