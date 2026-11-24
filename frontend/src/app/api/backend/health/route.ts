import { NextResponse } from "next/server";

const BACKEND_URL = process.env.SUPER_SCHOLAR_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(new URL("/health", BACKEND_URL), { cache: "no-store", signal: AbortSignal.timeout(4_000) });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json({ status: "offline", message: error instanceof Error ? error.message : String(error) }, { status: 503 });
  }
}
