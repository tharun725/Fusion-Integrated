/** Wire types for the ELM API.
 *
 *  Leave day counts are NUMBERS (floats), not strings: a half-day CL
 *  consumes 0.5 and a continuous-count interval is integral, so the
 *  fractional part carries meaning and must survive the round trip.
 */

export interface Page<T> {
  results: T[];
  next: string | null;
  previous: string | null;
}

/** The closed set ELM supports (BR-EL-001). */
export type LeaveCategory = "CL" | "RH" | "SCL" | "EL" | "COL" | "VL";

export const CATEGORY_LABELS: Record<LeaveCategory, string> = {
  CL: "Casual Leave",
  RH: "Restricted Holiday",
  SCL: "Special Casual Leave",
  EL: "Earned Leave",
  COL: "Commuted Leave",
  VL: "Vacation Leave",
};

/** Categories the Unit Head decides outright (BR-EL-016). */
export const UNIT_HEAD_FINAL: LeaveCategory[] = ["CL", "RH"];

export type LeaveStatus =
  | "draft"
  | "awaiting_substitute_response"
  | "applicant_action_required"
  | "awaiting_unit_head_review"
  | "awaiting_establishment_routing"
  | "awaiting_final_sanction_decision"
  | "awaiting_director_self_sanction"
  | "approved"
  | "rejected"
  | "withdrawn"
  | "ongoing"
  | "cancelled";

/** Statuses where withdrawal is still open (BR-EL-022). */
export const PENDING_STATUSES: LeaveStatus[] = [
  "draft",
  "awaiting_substitute_response",
  "applicant_action_required",
  "awaiting_unit_head_review",
  "awaiting_establishment_routing",
  "awaiting_final_sanction_decision",
  "awaiting_director_self_sanction",
];

export interface LeaveApplication {
  id: number;
  user_id: number;
  category: LeaveCategory;
  start_date: string;
  end_date: string;
  half_day: "" | "first" | "second";
  purpose: string;
  leave_year: string;
  days_requested: number;
  station_leave: boolean;
  station_leave_details: string;
  substitute_required: boolean;
  applicant_unit: number | null;
  applicant_designation: string;
  applicant_kind: "faculty" | "staff" | "";
  status: LeaveStatus;
  recommendation: "" | "recommended" | "not_recommended";
  decided_by_user_id: number | null;
  decided_at: string | null;
  decision_reason: string;
  withdrawn_reason: string;
  created_at: string;
  updated_at: string;
}

export interface LeaveBalance {
  id: number;
  user_id: number;
  category: LeaveCategory;
  leave_year: string;
  entitled: number;
  opening: number;
  used: number;
  lapsed: number;
  available: number;
  created_at: string;
  updated_at: string;
}

export interface LeaveTransaction {
  id: number;
  user_id: number;
  category: LeaveCategory;
  leave_year: string;
  kind: string;
  amount: number;
  reference_id: number | null;
  reference_kind: string;
  note: string;
  created_at: string;
}

export interface SubstituteAssignment {
  id: number;
  kind: "leave" | "extension";
  application: number | null;
  extension: number | null;
  applicant_user_id: number;
  substitute_user_id: number;
  responsibility_start: string;
  responsibility_end: string;
  response: "pending" | "accepted" | "declined";
  responded_at: string | null;
  decline_reason: string;
  created_at: string;
}

export interface LeaveCancellation {
  id: number;
  leave: number;
  user_id: number;
  reason: string;
  requested_on: string;
  status: string;
  decided_by_user_id: number | null;
  decided_at: string | null;
  decision_reason: string;
}

export interface LeaveExtension {
  id: number;
  leave: number;
  user_id: number;
  additional_start: string;
  additional_end: string;
  purpose: string;
  additional_days: number;
  substitute_required: boolean;
  status: string;
  decision_reason: string;
}

export interface ResumptionRecord {
  id: number;
  leave: number;
  user_id: number;
  actual_resumption_date: string;
  details: string;
  submitted_at: string;
  status: string;
  review_note: string;
}

export interface ElmNotification {
  id: number;
  user_id: number;
  topic: string;
  subject: string;
  body: string;
  reference_kind: string;
  reference_id: number | null;
  created_at: string;
}

export interface OrgUnit {
  id: number;
  code: string;
  name: string;
  kind: "department" | "section" | "office";
  parent: number | null;
  unit_head_user_id: number | null;
}

export interface EmployeeProfile {
  id: number;
  user_id: number;
  category: "faculty" | "staff";
  designation: string;
  unit: number | null;
}

export interface VacationPeriod {
  id: number;
  academic_year: string;
  label: string;
  start_date: string;
  end_date: string;
}

export interface HolidayCalendar {
  id: number;
  year: string;
  label: string;
  is_published: boolean;
  published_at: string | null;
  is_effective: boolean;
}

export interface Holiday {
  id: number;
  calendar: number;
  date: string;
  label: string;
  is_restricted_holiday: boolean;
  is_closed: boolean;
}

export interface LeavePolicy {
  id: number;
  key: string;
  value: string;
  description: string;
}

export interface SanctionHierarchy {
  id: number;
  category: string;
  step_order: number;
  role: string;
  is_establishment: boolean;
}

export interface SlaThresholds {
  task_class?: string;
  reminder?: number;
  escalation?: number;
  [taskClass: string]: unknown;
}

export interface YearEndSummary {
  leave_year: string;
  accounts: number;
  lapsed_days: number;
  converted_vl_days: number;
  carried_forward_days: number;
  exceptions: string[];
}