"use client";

import type { MaterialAnalysis, MaterialRecord, ResearchProject } from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_SUPER_SCHOLAR_BACKEND_URL ?? "http://127.0.0.1:8000";

async function checked(response: Response) {
  if (response.ok) return response;
  const text = await response.text();
  throw new Error(`Backend ${response.status}: ${text || response.statusText}`);
}

export async function checkBackendHealth() {
  const response = await checked(await fetch(`${BACKEND_URL}/health`, { cache: "no-store", signal: AbortSignal.timeout(4_000) }));
  return response.json() as Promise<{status:string;service:string;database:string;storage:string}>;
}


export interface ServerMaterialRecord {
  id: string;
  projectId: string;
  name: string;
  mimeType: string;
  extension: string;
  size: number;
  kind: MaterialRecord["kind"];
  sha256: string;
  analysis: MaterialAnalysis;
  createdAt: string;
  updatedAt: string;
  downloadUrl: string;
  textAvailable: boolean;
}

export async function getProjectFromServer(projectId: string) {
  const response = await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}`, { cache: "no-store" });
  if (response.status === 404) return null;
  return (await checked(response)).json() as Promise<ResearchProject>;
}

export async function listProjectsFromServer() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects?include_archived=true`, { cache: "no-store" }));
  return response.json() as Promise<ResearchProject[]>;
}

export async function listMaterialsFromServer(projectId: string) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}/materials`, { cache: "no-store" }));
  return response.json() as Promise<ServerMaterialRecord[]>;
}

export async function downloadMaterialFromServer(materialId: string) {
  return (await checked(await fetch(`${BACKEND_URL}/api/v1/materials/${encodeURIComponent(materialId)}/download`, { cache: "no-store" }))).blob();
}

export async function loadMaterialTextFromServer(materialId: string) {
  return (await checked(await fetch(`${BACKEND_URL}/api/v1/materials/${encodeURIComponent(materialId)}/text`, { cache: "no-store" }))).text();
}

export async function syncProjectSnapshot(project: ResearchProject) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(project.id)}/snapshot`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(project),
  }));
  return response.json();
}

export async function deleteProjectOnServer(projectId: string) {
  const response = await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
  if (response.status === 404) return;
  await checked(response);
}

export async function uploadMaterialToServer(projectId: string, record: MaterialRecord, file: File) {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("material_id", record.id);
  form.append("kind", record.kind);
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}/materials`, {
    method: "POST",
    body: form,
  }));
  return response.json();
}

export async function syncMaterialAnalysis(materialId: string, analysis: MaterialAnalysis, extractedText: string) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/materials/${encodeURIComponent(materialId)}/analysis`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ analysis, extracted_text: extractedText }),
  }));
  return response.json();
}

export async function deleteMaterialOnServer(materialId: string) {
  const response = await fetch(`${BACKEND_URL}/api/v1/materials/${encodeURIComponent(materialId)}`, { method: "DELETE" });
  if (response.status === 404) return;
  await checked(response);
}

export async function getResearchCapabilities() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/research/capabilities`, { cache: "no-store" }));
  return response.json() as Promise<import("./types").ResearchCapabilities>;
}

export async function startResearchAnalysis(projectId: string) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}/research-analysis`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ consent_external_processing: true }),
  }));
  return response.json() as Promise<import("./types").ResearchAnalysisRun>;
}

export async function getResearchAnalysis(runId: string) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/research-analysis/${encodeURIComponent(runId)}`, { cache: "no-store" }));
  return response.json() as Promise<import("./types").ResearchAnalysisRun>;
}

export async function getLatestResearchAnalysis(projectId: string) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}/research-analysis/latest`, { cache: "no-store" }));
  return response.json() as Promise<import("./types").ResearchAnalysisRun | null>;
}

export function researchArtifactUrl(relativeUrl: string) {
  if (/^https?:\/\//.test(relativeUrl)) return relativeUrl;
  return `${BACKEND_URL}${relativeUrl}`;
}

export function materialPreviewUrl(materialId: string, page?: number) {
  const base = `${BACKEND_URL}/api/v1/materials/${encodeURIComponent(materialId)}/preview`;
  return page ? `${base}#page=${page}&zoom=page-width` : base;
}

export function materialPageImageUrl(materialId: string, page: number) {
  return `${BACKEND_URL}/api/v1/materials/${encodeURIComponent(materialId)}/pages/${page}/preview.png`;
}


export async function getIntegrationSettings() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/integrations`, { cache: "no-store" }));
  return response.json() as Promise<import("./types").IntegrationSettings>;
}

export async function getIntegrationPresets() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/integrations/presets`, { cache: "no-store" }));
  return response.json() as Promise<Record<string, Record<string, unknown>>>;
}

export async function saveIntegrationSettings(payload: import("./types").IntegrationSettingsUpdate) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/integrations`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  }));
  return response.json() as Promise<import("./types").IntegrationSettings>;
}

export async function testAIIntegration() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/integrations/test-ai`, { method: "POST" }));
  return response.json() as Promise<import("./types").AIConnectionTest>;
}

export async function testOCRIntegration() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/integrations/test-ocr`, { method: "POST" }));
  return response.json() as Promise<import("./types").OCRConnectionTest>;
}


export async function getScholarlySettings() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/scholarly`, { cache: "no-store" }));
  return response.json() as Promise<import("./types").ScholarlyDataSettings>;
}

export async function saveScholarlySettings(payload: import("./types").ScholarlyDataSettingsUpdate) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/scholarly`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  }));
  return response.json() as Promise<import("./types").ScholarlyDataSettings>;
}

export async function testScholarlySources() {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/settings/scholarly/test`, { method: "POST" }));
  return response.json() as Promise<import("./types").ScholarlyConnectionTest>;
}


export async function requestVenueRecommendations(
  projectId: string,
  profile: import("./types").ResearchProfile,
  preferences: import("./types").PublicationPreferences,
) {
  const response = await checked(await fetch(`${BACKEND_URL}/api/v1/projects/${encodeURIComponent(projectId)}/recommendations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ profile, preferences }),
  }));
  return response.json() as Promise<import("./types").RecommendationRun>;
}
