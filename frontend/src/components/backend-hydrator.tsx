"use client";

import { useEffect, useRef } from "react";
import {
  listMaterialsFromServer,
  listProjectsFromServer,
  loadMaterialTextFromServer,
  syncProjectSnapshot,
} from "@/lib/backend-client";
import { saveText } from "@/lib/storage";
import type { MaterialRecord } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

/**
 * Reconciles durable backend state with the V1 local-first store.
 * Existing browser state always wins for overlapping projects in this stage;
 * server-only projects/materials are restored into the browser workspace.
 */
export function BackendHydrator() {
  const hydrated = useAppStore((state) => state.hydrated);
  const mergeServerState = useAppStore((state) => state.mergeServerState);
  const ran = useRef(false);

  useEffect(() => {
    if (!hydrated || ran.current) return;
    ran.current = true;
    let cancelled = false;

    void (async () => {
      try {
        const serverProjects = await listProjectsFromServer();
        const serverMaterials: MaterialRecord[] = [];

        for (const project of serverProjects) {
          const materials = await listMaterialsFromServer(project.id);
          for (const material of materials) {
            const textStorageKey = material.textAvailable ? `text:${material.id}` : undefined;
            if (textStorageKey) {
              try {
                const text = await loadMaterialTextFromServer(material.id);
                await saveText(textStorageKey, text);
              } catch {
                // The raw material is still recoverable from the backend even if
                // its extracted text has gone missing. Do not invent text here.
              }
            }
            serverMaterials.push({
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
        }

        if (cancelled) return;
        mergeServerState(serverProjects, serverMaterials);

        // Browser-local projects may include V1 work that predates the backend.
        // Mirror those snapshots after recovery without blocking the UI.
        for (const project of useAppStore.getState().projects) {
          void syncProjectSnapshot(project).catch(() => undefined);
        }
      } catch {
        // Offline/local-only use remains fully supported. BackendStatus exposes
        // connectivity to the user rather than showing a false success state.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [hydrated, mergeServerState]);

  return null;
}
