import type { PublicationPreferences, RecommendationResult, ResearchProfile, Venue } from "./types";

/**
 * @deprecated Since V3.7 venue ranking is intentionally backend-owned.
 *
 * The old browser implementation gave every venue in the same broad CCF area a
 * large fixed score (for example, unrelated AI venues could all become 72).  Keep
 * this symbol only as a loud migration guard for downstream imports; new code must
 * call requestVenueRecommendations(), which combines CCF/CCFDDL constraints with
 * OpenAlex scholarly semantic evidence.
 */
export function rankVenues(
  _profile: ResearchProfile,
  _preferences: PublicationPreferences,
  _venues: Venue[],
): RecommendationResult[] {
  throw new Error("rankVenues() is disabled in Super Scholar V3.7. Use the backend semantic recommendation endpoint.");
}
