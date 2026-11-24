"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { deleteMaterialOnServer, deleteProjectOnServer, syncProjectSnapshot } from "@/lib/backend-client";
import { DEFAULT_PREFERENCES } from "@/lib/constants";
import { uid } from "@/lib/utils";
import type { MaterialRecord, PublicationPreferences, RecommendationRun, ResearchProfile, ResearchProject, Venue } from "@/lib/types";

interface AppState {
  projects: ResearchProject[];
  materials: Record<string, MaterialRecord>;
  hydrated: boolean;
  setHydrated: (value: boolean) => void;
  createProject: (name: string, brief: string) => ResearchProject;
  updateProject: (id: string, patch: Partial<ResearchProject>) => void;
  renameProject: (id: string, name: string) => void;
  duplicateProject: (id: string) => ResearchProject | undefined;
  archiveProject: (id: string, archived?: boolean) => void;
  deleteProject: (id: string) => MaterialRecord[];
  addMaterial: (record: MaterialRecord) => void;
  updateMaterial: (id: string, patch: Partial<MaterialRecord>) => void;
  removeMaterial: (id: string) => MaterialRecord | undefined;
  setProfile: (projectId: string, profile: ResearchProfile) => void;
  setPreferences: (projectId: string, preferences: PublicationPreferences) => void;
  setRecommendationRun: (projectId: string, run: RecommendationRun) => void;
  updateRecommendationRun: (projectId: string, patch: Partial<RecommendationRun>) => void;
  toggleCompareVenue: (projectId: string, venueId: string) => void;
  selectVenue: (projectId: string, venue: Venue) => void;
  mergeServerState: (projects: ResearchProject[], materials: MaterialRecord[]) => void;
}

function normalizePreferences(input: Partial<PublicationPreferences> | undefined): PublicationPreferences {
  const base = structuredClone(DEFAULT_PREFERENCES);
  if (!input) return base;
  return {
    ...base,
    ...input,
    ccfRanks: { ...base.ccfRanks, ...input.ccfRanks },
    coreRanks: { ...base.coreRanks, ...input.coreRanks },
    deadlineMonths: { ...base.deadlineMonths, ...input.deadlineMonths },
    locations: { ...base.locations, ...input.locations },
    wosIndexes: { ...base.wosIndexes, ...input.wosIndexes },
    jcrQuartiles: { ...base.jcrQuartiles, ...input.jcrQuartiles },
    impactFactor: { ...base.impactFactor, ...input.impactFactor, value: { ...base.impactFactor.value, ...input.impactFactor?.value } },
    openAccess: { ...base.openAccess, ...input.openAccess },
    apcCny: { ...base.apcCny, ...input.apcCny, value: { ...base.apcCny.value, ...input.apcCny?.value } },
    reviewDays: { ...base.reviewDays, ...input.reviewDays },
    chinaIndexes: { ...base.chinaIndexes, ...input.chinaIndexes },
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => {
      const pushProject = (id: string) => {
        const project = get().projects.find((item) => item.id === id);
        if (!project) return;
        void syncProjectSnapshot(project).catch((error) => {
          console.warn("Super Scholar backend project sync failed", error);
        });
      };

      return {
        projects: [],
        materials: {},
        hydrated: false,
        setHydrated: (hydrated) => set({ hydrated }),
        createProject: (name, brief) => {
          const now = new Date().toISOString();
          const project: ResearchProject = {
            id: uid("project"),
            name: name.trim(),
            brief: brief.trim(),
            createdAt: now,
            updatedAt: now,
            status: "draft",
            archived: false,
            materialIds: [],
            preferences: structuredClone(DEFAULT_PREFERENCES),
            comparisonVenueIds: [],
          };
          set((state) => ({ projects: [project, ...state.projects] }));
          pushProject(project.id);
          return project;
        },
        updateProject: (id, patch) => {
          set((state) => ({
            projects: state.projects.map((project) => project.id === id ? { ...project, ...patch, updatedAt: new Date().toISOString() } : project),
          }));
          pushProject(id);
        },
        renameProject: (id, name) => get().updateProject(id, { name: name.trim() }),
        duplicateProject: (id) => {
          const source = get().projects.find((project) => project.id === id);
          if (!source) return undefined;
          const now = new Date().toISOString();
          const project: ResearchProject = {
            ...structuredClone(source),
            id: uid("project"),
            name: `${source.name} · 副本`,
            createdAt: now,
            updatedAt: now,
            materialIds: [],
            profile: undefined,
            recommendationRun: undefined,
            comparisonVenueIds: [],
            selectedVenueId: undefined,
            status: "draft",
          };
          set((state) => ({ projects: [project, ...state.projects] }));
          pushProject(project.id);
          return project;
        },
        archiveProject: (id, archived = true) => get().updateProject(id, { archived }),
        deleteProject: (id) => {
          const project = get().projects.find((item) => item.id === id);
          const removed = project?.materialIds.map((mid) => get().materials[mid]).filter(Boolean) ?? [];
          set((state) => {
            const nextMaterials = { ...state.materials };
            for (const material of removed) delete nextMaterials[material.id];
            return { projects: state.projects.filter((item) => item.id !== id), materials: nextMaterials };
          });
          void deleteProjectOnServer(id).catch((error) => console.warn("Super Scholar backend project delete failed", error));
          return removed;
        },
        addMaterial: (record) => {
          set((state) => ({
            materials: { ...state.materials, [record.id]: record },
            projects: state.projects.map((project) => project.id === record.projectId ? { ...project, materialIds: [...project.materialIds, record.id], status: "materials", updatedAt: new Date().toISOString() } : project),
          }));
          pushProject(record.projectId);
        },
        updateMaterial: (id, patch) => set((state) => ({
          materials: { ...state.materials, [id]: { ...state.materials[id], ...patch, updatedAt: new Date().toISOString() } },
        })),
        removeMaterial: (id) => {
          const record = get().materials[id];
          if (!record) return undefined;
          set((state) => {
            const next = { ...state.materials };
            delete next[id];
            return {
              materials: next,
              projects: state.projects.map((project) => project.id === record.projectId ? { ...project, materialIds: project.materialIds.filter((mid) => mid !== id), updatedAt: new Date().toISOString() } : project),
            };
          });
          void deleteMaterialOnServer(id).catch((error) => console.warn("Super Scholar backend material delete failed", error));
          pushProject(record.projectId);
          return record;
        },
        setProfile: (projectId, profile) => get().updateProject(projectId, { profile, status: "profile_ready", recommendationRun: undefined, comparisonVenueIds: [], selectedVenueId: undefined }),
        setPreferences: (projectId, preferences) => get().updateProject(projectId, { preferences, status: "preferences_ready", recommendationRun: undefined, comparisonVenueIds: [], selectedVenueId: undefined }),
        setRecommendationRun: (projectId, run) => get().updateProject(projectId, { recommendationRun: run, status: run.status === "running" ? "recommending" : "recommendations_ready", ...(run.status === "running" ? { comparisonVenueIds: [], selectedVenueId: undefined } : {}) }),
        updateRecommendationRun: (projectId, patch) => {
          const project = get().projects.find((item) => item.id === projectId);
          if (!project?.recommendationRun) return;
          const run = { ...project.recommendationRun, ...patch };
          get().updateProject(projectId, { recommendationRun: run, status: run.status === "ready" ? "recommendations_ready" : run.status === "running" ? "recommending" : project.status });
        },
        toggleCompareVenue: (projectId, venueId) => {
          const project = get().projects.find((item) => item.id === projectId);
          if (!project) return;
          const exists = project.comparisonVenueIds.includes(venueId);
          const next = exists ? project.comparisonVenueIds.filter((id) => id !== venueId) : [...project.comparisonVenueIds, venueId].slice(-5);
          get().updateProject(projectId, { comparisonVenueIds: next });
        },
        selectVenue: (projectId, venue) => get().updateProject(projectId, { selectedVenueId: venue.id, status: "venue_selected" }),
        mergeServerState: (serverProjects, serverMaterials) => {
          set((state) => {
            const localProjectIds = new Set(state.projects.map((project) => project.id));
            const importedProjects = serverProjects
              .filter((project) => !localProjectIds.has(project.id))
              .map((project) => ({
                ...project,
                preferences: normalizePreferences(project.preferences),
                comparisonVenueIds: project.comparisonVenueIds ?? [],
                materialIds: project.materialIds ?? [],
                selectedVenueId: project.selectedVenueId ?? undefined,
                recommendationRun: project.recommendationRun ?? undefined,
                profile: project.profile ?? undefined,
              }));
            const nextMaterials = { ...state.materials };
            for (const material of serverMaterials) {
              if (!nextMaterials[material.id]) nextMaterials[material.id] = material;
              else if (nextMaterials[material.id].serverSync !== "error") {
                nextMaterials[material.id] = { ...nextMaterials[material.id], serverSync: "synced", serverSyncError: undefined };
              }
            }
            const serverById = new Map(serverProjects.map((project) => [project.id, project]));
            const reconciledLocal = state.projects.map((project) => {
              const server = serverById.get(project.id);
              if (!server) return project;
              return { ...project, materialIds: Array.from(new Set([...project.materialIds, ...(server.materialIds ?? [])])) };
            });
            return {
              projects: [...reconciledLocal, ...importedProjects].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
              materials: nextMaterials,
            };
          });
        },
      };
    },
    {
      name: "super-scholar-v1",
      partialize: (state) => ({ projects: state.projects, materials: state.materials }),
      onRehydrateStorage: () => (state) => state?.setHydrated(true),
    },
  ),
);
