import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function uid(prefix = "id") {
  return `${prefix}_${crypto.randomUUID()}`;
}

export function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDate(iso: string) {
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" }).format(new Date(iso));
}

export function daysUntil(iso?: string, timezone?: string) {
  if (!iso || iso === "TBD") return undefined;
  const target = parseCcfDate(iso, timezone);
  if (!target) return undefined;
  return Math.ceil((target.getTime() - Date.now()) / 86_400_000);
}

export function parseCcfDate(value: string, timezone?: string) {
  if (!value || value === "TBD") return undefined;
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!match) {
    const fallback = new Date(normalized);
    return Number.isNaN(fallback.getTime()) ? undefined : fallback;
  }
  const [, y, mo, d, h, mi, sec = "00"] = match;
  const localAsUtc = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(sec));
  const zone = (timezone ?? "UTC").trim();

  let offsetMinutes = 0;
  if (/^AoE$/i.test(zone)) offsetMinutes = -12 * 60;
  else if (/^PT$/i.test(zone)) {
    const getPacificOffset = (instant: number) => {
      const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: "America/Los_Angeles",
        timeZoneName: "longOffset",
        year: "numeric", month: "2-digit", day: "2-digit"
      }).formatToParts(new Date(instant));
      const name = parts.find((part) => part.type === "timeZoneName")?.value ?? "GMT-08:00";
      const m = name.match(/GMT([+-])(\d{2}):(\d{2})/);
      if (!m) return -8 * 60;
      const sign = m[1] === "+" ? 1 : -1;
      return sign * (Number(m[2]) * 60 + Number(m[3]));
    };
    offsetMinutes = getPacificOffset(localAsUtc);
    const firstUtc = localAsUtc - offsetMinutes * 60_000;
    offsetMinutes = getPacificOffset(firstUtc);
  } else {
    const z = zone.match(/^UTC(?:([+-])(\d{1,2})(?::?(\d{2}))?)?$/i);
    if (z?.[1]) {
      const sign = z[1] === "+" ? 1 : -1;
      offsetMinutes = sign * (Number(z[2]) * 60 + Number(z[3] ?? 0));
    }
  }

  const date = new Date(localAsUtc - offsetMinutes * 60_000);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export function safeHostname(url?: string) {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function normalizeText(text: string) {
  return text
    .replace(/\u0000/g, " ")
    .replace(/[\t\r]+/g, " ")
    .replace(/ +/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
