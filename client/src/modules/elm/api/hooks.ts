/** Data access for the ELM module.
 *
 *  Every mutation invalidates the keys it can affect. Getting that wrong
 *  shows up as an enabled "Approve" button on a request that has already
 *  been decided, so each mutation invalidates the whole module prefix.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { http } from "../../../lib/http";
import type {
  EmployeeProfile, ElmNotification, Holiday, HolidayCalendar, LeaveApplication,
  LeaveBalance, LeaveCancellation, LeaveExtension, LeavePolicy,
  LeaveTransaction, OrgUnit, Page, ResumptionRecord,
  SanctionHierarchy, SlaThresholds, SubstituteAssignment, VacationPeriod,
  YearEndSummary,
} from "./types";

const KEY = "elm";

export const keys = {
  applications: () => [KEY, "applications"] as const,
  application: (id: number) => [KEY, "application", id] as const,
  balances: () => [KEY, "balances"] as const,
  transactions: () => [KEY, "transactions"] as const,
  notifications: () => [KEY, "notifications"] as const,
  substituteRequests: () => [KEY, "substitute-requests"] as const,
  queue: (stage: string) => [KEY, "queue", stage] as const,
  policy: () => [KEY, "policy"] as const,
  hierarchy: () => [KEY, "hierarchy"] as const,
  calendars: () => [KEY, "calendars"] as const,
  holidays: () => [KEY, "holidays"] as const,
  employees: () => [KEY, "employees"] as const,
  units: () => [KEY, "org-units"] as const,
  vacations: () => [KEY, "vacation-periods"] as const,
  sla: () => [KEY, "sla"] as const,
};

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: [KEY] });
}

export function useMyApplications() {
  return useQuery({
    queryKey: keys.applications(),
    queryFn: async () =>
      (await http.get<Page<LeaveApplication>>("/leave/applications")).data,
    staleTime: 15_000,
  });
}

export function useApplication(id: number | undefined) {
  return useQuery({
    queryKey: keys.application(id ?? 0),
    queryFn: async () =>
      (await http.get<LeaveApplication>(
        `/leave/applications/${id}`)).data,
    enabled: id != null,
  });
}

export function useBalances() {
  return useQuery({
    queryKey: keys.balances(),
    queryFn: async () =>
      (await http.get<Page<LeaveBalance>>("/leave/balances")).data,
    staleTime: 15_000,
  });
}

export function useTransactions() {
  return useQuery({
    queryKey: keys.transactions(),
    queryFn: async () =>
      (await http.get<Page<LeaveTransaction>>(
        "/leave/balances/history")).data,
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: keys.notifications(),
    queryFn: async () =>
      (await http.get<Page<ElmNotification>>(
        "/leave/notifications")).data,
  });
}

export function useSubstituteRequests() {
  return useQuery({
    queryKey: keys.substituteRequests(),
    queryFn: async () =>
      (await http.get<Page<SubstituteAssignment>>(
        "/leave/substitute-requests")).data,
  });
}

/** A review queue for one stage: unit-head, establishment or final. */
export function useQueue(stage: "unit-head" | "establishment" | "final") {
  return useQuery({
    queryKey: keys.queue(stage),
    queryFn: async () =>
      (await http.get<Page<LeaveApplication>>(
        `/leave/reviews/${stage}`)).data,
    staleTime: 10_000,
  });
}

export function usePolicy() {
  return useQuery({
    queryKey: keys.policy(),
    queryFn: async () =>
      (await http.get<Page<LeavePolicy>>("/leave/policy")).data,
  });
}

export function useHierarchy() {
  return useQuery({
    queryKey: keys.hierarchy(),
    queryFn: async () =>
      (await http.get<Page<SanctionHierarchy>>(
        "/leave/hierarchy")).data,
  });
}

export function useCalendars() {
  return useQuery({
    queryKey: keys.calendars(),
    queryFn: async () =>
      (await http.get<Page<HolidayCalendar>>("/leave/calendar")).data,
  });
}

export function useHolidays() {
  return useQuery({
    queryKey: keys.holidays(),
    queryFn: async () =>
      (await http.get<Page<Holiday>>("/leave/calendar/holidays")).data,
  });
}

export function useEmployees() {
  return useQuery({
    queryKey: keys.employees(),
    queryFn: async () =>
      (await http.get<Page<EmployeeProfile>>("/leave/employees")).data,
    staleTime: 60_000,
  });
}

export function useOrgUnits() {
  return useQuery({
    queryKey: keys.units(),
    queryFn: async () =>
      (await http.get<Page<OrgUnit>>("/leave/org-units")).data,
    staleTime: 60_000,
  });
}

export function useVacationPeriods() {
  return useQuery({
    queryKey: keys.vacations(),
    queryFn: async () =>
      (await http.get<Page<VacationPeriod>>(
        "/leave/vacation-periods")).data,
    staleTime: 60_000,
  });
}

export function useSlaThresholds() {
  return useQuery({
    queryKey: keys.sla(),
    queryFn: async () =>
      (await http.get<SlaThresholds>("/leave/sla")).data,
  });
}

// -- Mutations -----------------------------------------------------------

export interface ApplyPayload {
  category: string;
  start_date: string;
  end_date: string;
  half_day?: string;
  purpose?: string;
  station_leave?: boolean;
  station_leave_details?: string;
  substitute_required?: boolean;
  substitute_user_id?: number | null;
}

export type ReviewPayload = {
  outcome?: string;
  recommendation?: string;
  reason?: string;
};

/** Apply for leave (EL-UC-001). */
export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ApplyPayload) =>
      (await http.post<LeaveApplication>(
        "/leave/applications/apply", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Withdraw a pending request (EL-UC-007). */
export function useWithdraw() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason?: string }) =>
      (await http.post<LeaveApplication>(
        `/leave/applications/${id}/withdraw`, { reason })).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Accept or decline a substitute assignment (EL-UC-002). */
export function useRespondToSubstitute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      { id, accept, decline_reason }:
      { id: number; accept: boolean; decline_reason?: string }) =>
      (await http.post<SubstituteAssignment>(
        `/leave/substitute-requests/${id}/respond`,
        { accept, decline_reason: decline_reason ?? "" })).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Nominate a replacement substitute after a decline (EL-UC-019). */
export function useNominateReplacement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      { id, substitute_user_id }:
      { id: number; substitute_user_id: number }) =>
      (await http.post<SubstituteAssignment>(
        `/leave/applications/${id}/replacement`,
        { substitute_user_id })).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Record the Unit Head's decision or recommendation (EL-UC-003). */
export function useUnitHeadReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: ReviewPayload }) =>
      (await http.post<LeaveApplication>(
        `/leave/applications/${id}/unit-head-review`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Verify and route at Establishment (EL-UC-004). */
export function useEstablishmentRoute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await http.post<LeaveApplication>(
        `/leave/applications/${id}/establishment-route`,
        {})).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Make the final sanctioning decision (EL-UC-005). */
export function useFinalSanction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: ReviewPayload }) =>
      (await http.post<LeaveApplication>(
        `/leave/applications/${id}/final-sanction`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Request cancellation of approved leave (EL-UC-008). */
export function useRequestCancellation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }:
      { id: number; reason?: string }) =>
      (await http.post<LeaveCancellation>(
        `/leave/applications/${id}/cancel`,
        { reason: reason ?? "" })).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Decide a cancellation at whatever stage it has reached. */
export function useReviewCancellation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: ReviewPayload }) =>
      (await http.post<LeaveCancellation>(
        `/leave/cancellations/${id}/review`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Request an extension of ongoing leave (EL-UC-009). */
export function useRequestExtension() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: Record<string, unknown> }) =>
      (await http.post<LeaveExtension>(
        `/leave/applications/${id}/extend`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Decide an extension at whatever stage it has reached. */
export function useReviewExtension() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: ReviewPayload }) =>
      (await http.post<LeaveExtension>(
        `/leave/extensions/${id}/review`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Submit actual resumption of duty (EL-UC-010). */
export function useSubmitResumption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: Record<string, unknown> }) =>
      (await http.post<ResumptionRecord>(
        `/leave/applications/${id}/resumption`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Review a submitted resumption (EL-UC-011). */
export function useReviewResumption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }:
      { id: number; body: ReviewPayload }) =>
      (await http.post<ResumptionRecord>(
        `/leave/resumptions/${id}/review`, body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Revise a current policy parameter (EL-UC-014). */
export function useSetPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<LeavePolicy>("/leave/policy", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Revise one sanctioning step (EL-UC-014). */
export function useSetHierarchyStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<SanctionHierarchy>(
        "/leave/hierarchy", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Create a holiday/RH calendar (EL-UC-015). */
export function useCreateCalendar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<HolidayCalendar>(
        "/leave/calendar", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Publish a replacement calendar (EL-UC-015). */
export function usePublishCalendar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await http.post<HolidayCalendar>(
        `/leave/calendar/${id}/publish`, {})).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Record already-sanctioned offline leave (EL-UC-016). */
export function useRecordOffline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post("/leave/offline-records", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Configure SLA thresholds (EL-UC-018). */
export function useSetSla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<SlaThresholds>("/leave/sla", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Run event-triggered SLA processing (EL-UC-021). */
export function useRunSla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (taskClass?: string) =>
      (await http.post("/leave/sla/process",
        taskClass ? { task_class: taskClass } : {})).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Execute year-end leave processing (EL-UC-020). */
export function useRunYearEnd() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (leaveYear: string) =>
      (await http.post<YearEndSummary>(
        "/leave/year-end", { leave_year: leaveYear })).data,
    onSettled: () => invalidateAll(qc),
  });
}

/** Create or revise an organisational unit (EL-UC-014). */
export function useCreateUnit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<OrgUnit>("/leave/org-units", body)).data,
    onSettled: () => invalidateAll(qc),
  });
}
