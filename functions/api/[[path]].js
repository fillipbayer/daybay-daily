/**
 * DayBay Daily — Cloudflare Pages Function
 * Faz proxy de todas as chamadas /api/* para o backend Railway
 *
 * Configure a variável de ambiente BACKEND_URL no painel do Cloudflare Pages
 * com a URL do seu serviço Railway (ex: https://daybay-backend.up.railway.app)
 */
export async function onRequest(context) {
  const { request, env } = context;

  const backendUrl = env.BACKEND_URL;
  if (!backendUrl) {
    return new Response(
      JSON.stringify({ error: "BACKEND_URL não configurada nas variáveis de ambiente do Cloudflare Pages." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }

  // Monta a URL de destino no Railway
  const url = new URL(request.url);
  const targetUrl = backendUrl.replace(/\/$/, "") + url.pathname + url.search;

  // Clona os headers (remove headers problemáticos)
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("cf-ray");
  headers.delete("cf-connecting-ip");
  headers.delete("cf-ipcountry");
  headers.delete("cf-visitor");

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "follow",
    });

    // Retorna a resposta do Railway para o cliente
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Access-Control-Allow-Origin", "*");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "Erro ao conectar ao backend.", detail: err.message }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

// Suporte a CORS preflight
export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400",
    },
  });
}
