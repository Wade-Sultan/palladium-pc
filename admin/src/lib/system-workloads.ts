/**
 * The workloads a family may be offered for. Mirrors SystemWorkload in
 * backend/app/models/systems.py: the offer rules read these exact strings, so
 * a value missing from that enum is stored but never matched.
 */
export const SYSTEM_WORKLOADS = [
  { value: 'llm_inference', label: 'Local LLM inference' },
  { value: 'llm_training', label: 'LLM fine-tuning' },
  { value: 'video_editing', label: 'Video editing' },
  { value: 'music_production', label: 'Music production' },
  { value: 'gaming', label: 'Gaming (allows offers to users who game)' },
] as const;
