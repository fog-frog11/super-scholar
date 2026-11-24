"use client";

import { getProjectFromServer, listMaterialsFromServer, loadMaterialTextFromServer } from "./backend-client";
import { saveText } from "./storage";
import type { MaterialRecord, ResearchProject } from "./types";
import { useAppStore } from "@/store/use-app-store";

export async function recoverProjectFromServer(projectId: string): Promise<ResearchProject | null> {
  const project = await getProjectFromServer(projectId);
  if (!project) return null;
  const serverMaterials = await listMaterialsFromServer(projectId);
  const materials: MaterialRecord[] = [];
  for (const material of serverMaterials) {
    const textStorageKey = material.textAvailable ? `text:${material.id}` : undefined;
    if (textStorageKey) {
      try {
        const text = await loadMaterialTextFromServer(material.id);
        await saveText(textStorageKey, text);
      } catch {
        // The source file can still be restored from the backend later.
      }
    }
    materials.push({
      id: material.id,
      projectId: material.projectId,
      name: material.name,
      mimeType: material.mimeType,
      extension: material.extension,
      size: material.size,
      kind: material.kind,
      storageKey: `blob:${material.id}`,
      textStorageKey,
      createdAt: material.createdAt,
      updatedAt: material.updatedAt,
      analysis: material.analysis,
      serverSync: "synced",
    });
  }
  useAppStore.getState().mergeServerState([project], materials);
  return useAppStore.getState().projects.find((item)=>item.id===projectId) ?? project;
}
