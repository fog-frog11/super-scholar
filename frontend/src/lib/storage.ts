"use client";

import { del, get, set } from "idb-keyval";

export async function saveBlob(key: string, file: Blob) {
  await set(key, file);
}

export async function loadBlob(key: string) {
  return (await get<Blob>(key)) ?? null;
}

export async function saveText(key: string, text: string) {
  await set(key, text);
}

export async function loadText(key?: string) {
  if (!key) return "";
  return (await get<string>(key)) ?? "";
}

export async function deleteStored(key?: string) {
  if (key) await del(key);
}
