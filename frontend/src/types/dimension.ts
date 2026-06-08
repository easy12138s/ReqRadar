export type DimensionStatus = 'pending' | 'in_progress' | 'sufficient' | 'insufficient';

export interface DimensionState {
  dimension_id: string;
  status: DimensionStatus;
  evidence_count: number;
  draft_content: string | null;
}

export interface DimensionSummary {
  dimensions: DimensionState[];
  all_sufficient: boolean;
  weak_dimensions: string[];
}
