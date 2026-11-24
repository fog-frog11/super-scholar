import { NextResponse } from "next/server";

const BACKEND_URL = process.env.SUPER_SCHOLAR_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const refresh = incoming.searchParams.get("refresh");
  const target = new URL("/api/v1/venues/conferences", BACKEND_URL);
  if (refresh === "1" || refresh === "true") target.searchParams.set("refresh", "true");
  try {
    const response = await fetch(target, { cache: "no-store", signal: AbortSignal.timeout(25_000) });
    const text = await response.text();
    let body: unknown;
    try { body = JSON.parse(text); } catch { body = { detail: text || response.statusText }; }
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    return NextResponse.json({
      detail: {
        code: "backend_unavailable",
        message: error instanceof Error ? error.message : String(error),
        backend: BACKEND_URL,
      },
      items: [],
    }, { status: 503 });
  }
}
