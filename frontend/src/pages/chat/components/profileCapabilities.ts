import type { PipelineProfile } from "../../../types/api";

export type ProfileCapabilities = Readonly<{
  web: boolean;
  reasoning: boolean;
  agent: boolean;
  retrieval: boolean;
}>;

export type ProfileModeHint =
  | "local"
  | "web"
  | "reasoning"
  | "strictQuality"
  | "advanced"
  | "advancedReasoning";

const CAPABILITIES: Record<PipelineProfile, ProfileCapabilities> = {
  standard: { web: true, reasoning: true, agent: true, retrieval: true },
  strict_quality: { web: false, reasoning: false, agent: true, retrieval: true },
  advanced: { web: false, reasoning: true, agent: false, retrieval: true },
};

export function profileCapabilities(profile: PipelineProfile): ProfileCapabilities {
  return CAPABILITIES[profile];
}

export function profileModeHint(
  profile: PipelineProfile,
  options: Readonly<{ useWeb: boolean; useReasoning: boolean }>,
): ProfileModeHint {
  const capabilities = profileCapabilities(profile);

  if (profile === "strict_quality") {
    return "strictQuality";
  }
  if (profile === "advanced") {
    return capabilities.reasoning && options.useReasoning
      ? "advancedReasoning"
      : "advanced";
  }
  if (capabilities.web && options.useWeb) {
    return "web";
  }
  if (capabilities.reasoning && options.useReasoning) {
    return "reasoning";
  }
  return "local";
}
