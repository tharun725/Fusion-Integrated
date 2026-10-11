import { useState } from "react";
import {
  Badge, Button, Card, Container, Group, Modal, SegmentedControl,
  Stack, Text, Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCheck, FaInbox } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useEstablishmentRoute, useFinalSanction, useQueue,
  useUnitHeadReview,
} from "../api/hooks";
import {
  CATEGORY_LABELS, UNIT_HEAD_FINAL, type LeaveApplication,
} from "../api/types";

type Decision = {
  outcome?: "approve" | "reject";
  recommendation?: "recommended" | "not_recommended";
  reason?: string;
};

export default function QueuePage() {
  const [stage, setStage] = useState<"unit-head" | "establishment"
    | "final">("unit-head");
  const queue = useQueue(stage);
  const unitHead = useUnitHeadReview();
  const establish = useEstablishmentRoute();
  const sanction = useFinalSanction();

  const [target, setTarget] = useState<LeaveApplication | null>(null);
  const [mode, setMode] = useState<"final" | "recommend" | "route">(
    "final");
  const [reason, setReason] = useState("");
  const [recommendation, setRecommendation] = useState<
    "recommended" | "not_recommended">("recommended");
  const [outcome, setOutcome] = useState<"approve" | "reject">(
    "approve");

  if (queue.error) {
    return <Container size="xl"><ErrorState error={queue.error} /></Container>;
  }

  /** CL/RH are decided by the Unit Head; the rest are only recommended. */
  function decisionKind(a: LeaveApplication): "final" | "recommend" {
    return UNIT_HEAD_FINAL.includes(a.category) ? "final" : "recommend";
  }

  function openDecision(a: LeaveApplication) {
    setTarget(a);
    setReason("");
    setRecommendation("recommended");
    if (stage === "establishment") setMode("route");
    else setMode(decisionKind(a));
  }

  function payload(): Decision {
    return mode === "final"
      ? { outcome, reason }
      : mode === "recommend"
        ? { recommendation, reason }
        : { reason };
  }

  function submit() {
    if (!target) return;
    const body = payload();
    const onOk = (message: string) =>
      notifications.show({ message, color: "green" });
    const onErr = (e: unknown) =>
      notifications.show({ message: errorMessage(e), color: "red" });

    if (stage === "unit-head") {
      unitHead.mutate({ id: target.id, body }, {
        onSuccess: () => onOk("Recorded."),
        onError: onErr,
      });
    } else if (stage === "establishment") {
      establish.mutate(target.id, {
        onSuccess: () => onOk("Routed to the sanctioning authority."),
        onError: onErr,
      });
    } else {
      sanction.mutate({ id: target.id, body }, {
        onSuccess: () => onOk("Decision recorded."),
        onError: onErr,
      });
    }
  }

  const rows = queue.data?.results ?? [];

  return (
    <Container size="xl">
      <PageHeader
        title="Review Queue"
        subtitle="Requests waiting on you at this stage"
        action={
          <SegmentedControl
            value={stage}
            onChange={(v) =>
              setStage(v as "unit-head" | "establishment" | "final")}
            data={[
              { label: "Unit Head", value: "unit-head" },
              { label: "Establishment", value: "establishment" },
              { label: "Sanction", value: "final" },
            ]}
          />
        }
      />

      <Card padding="lg">
        <DataTable<LeaveApplication>
          rows={rows}
          loading={queue.isPending}
          rowKey={(r) => r.id}
          minWidth={900}
          empty={{
            icon: FaInbox,
            title: "Queue is clear",
            description: "Nothing is waiting at this stage.",
          }}
          columns={[
            {
              key: "id",
              header: "Ref",
              render: (r) => `#${r.id}`,
            },
            {
              key: "user_id",
              header: "Applicant",
              render: (r) => (
                <Stack gap={0}>
                  <Text>#{r.user_id}</Text>
                  <Text size="xs" c="dimmed">
                    {r.applicant_designation}
                  </Text>
                </Stack>
              ),
            },
            {
              key: "category",
              header: "Category",
              render: (r) => (
                <Badge variant="light" color="blue">
                  {CATEGORY_LABELS[r.category]}
                </Badge>
              ),
            },
            {
              key: "period",
              header: "Period",
              render: (r) => (
                <Stack gap={0}>
                  <Text>{r.start_date} → {r.end_date}</Text>
                  <Text size="xs" c="dimmed">
                    {r.days_requested} day
                    {r.days_requested === 1 ? "" : "s"}
                    {r.station_leave ? " · station leave" : ""}
                  </Text>
                </Stack>
              ),
            },
            {
              key: "recommendation",
              header: "Recommendation",
              render: (r) => r.recommendation
                ? r.recommendation.replace(/_/g, " ")
                : "—",
            },
            {
              key: "act",
              header: "",
              align: "right",
              render: (r) => (
                <Button size="xs" variant="light"
                  onClick={() => openDecision(r)}>
                  {stage === "establishment" ? "Route" : "Decide"}
                </Button>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        opened={Boolean(target)}
        onClose={() => setTarget(null)}
        title={target
          ? `Request #${target.id} — ${CATEGORY_LABELS[target.category]}`
          : ""}
      >
        <Stack>
          {target && (
            <Text size="sm" c="dimmed">
              {target.start_date} → {target.end_date} ·{" "}
              {target.days_requested} day
              {target.days_requested === 1 ? "" : "s"}
              <br />
              {target.purpose || "No purpose given."}
            </Text>
          )}

          {mode === "final" && (
            <SegmentedControl
              fullWidth
              value={outcome}
              onChange={(v) =>
                setOutcome(v as "approve" | "reject")}
              data={[
                { label: "Approve", value: "approve" },
                { label: "Reject", value: "reject" },
              ]}
            />
          )}

          {mode === "recommend" && (
            <Stack gap={4}>
              <Text size="sm" fw={600}>
                Recommendation
              </Text>
              <Text size="xs" c="dimmed">
                Not Recommended is not a final rejection; the request
                continues through the higher-sanction path.
              </Text>
              <SegmentedControl
                fullWidth
                value={recommendation}
                onChange={(v) => setRecommendation(
                  v as "recommended" | "not_recommended")}
                data={[
                  { label: "Recommended", value: "recommended" },
                  {
                    label: "Not Recommended",
                    value: "not_recommended",
                  },
                ]}
              />
            </Stack>
          )}

          {mode === "route" && (
            <Text size="sm" c="dimmed">
              Verify the routing context, then forward this request
              to the resolved sanctioning authority.
            </Text>
          )}

          <Textarea
            label="Reason"
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
            autosize
            minRows={2}
          />

          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => setTarget(null)}
            >
              Close
            </Button>
            <Button
              leftSection={<FaCheck size={12} />}
              loading={
                unitHead.isPending
                || establish.isPending
                || sanction.isPending
              }
              onClick={submit}
            >
              Record
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}