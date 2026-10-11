import { useState } from "react";
import {
  Badge, Button, Card, Container, Group, Modal, Stack, Text, Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaStamp } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useFinalSanction } from "../api/hooks";
import { useQueue } from "../api/hooks";
import { CATEGORY_LABELS, type LeaveApplication } from "../api/types";

export default function SanctionsPage() {
  const queue = useQueue("final");
  const sanction = useFinalSanction();
  const [target, setTarget] = useState<LeaveApplication | null>(null);
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState<"approve" | "reject">(
    "approve");

  if (queue.error) {
    return <Container size="xl"><ErrorState error={queue.error} /></Container>;
  }

  function submit() {
    if (!target) return;
    sanction.mutate({
      id: target.id,
      body: { outcome, reason },
    }, {
      onSuccess: () => {
        notifications.show({
          message: outcome === "approve"
            ? "Approved — the leave account has been updated."
            : "Rejected. The balance is unchanged.",
          color: outcome === "approve" ? "green" : "gray" });
        setTarget(null);
        setReason("");
      },
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  return (
    <Container size="xl">
      <PageHeader
        title="Sanction Queue"
        subtitle="Recommended requests awaiting your final sanctioning decision"
      />

      <Card padding="lg">
        <DataTable<LeaveApplication>
          rows={queue.data?.results ?? []}
          loading={queue.isPending}
          rowKey={(r) => r.id}
          minWidth={900}
          empty={{
            icon: FaStamp,
            title: "Nothing to sanction",
            description: "No request is waiting on your decision.",
          }}
          columns={[
            { key: "id", header: "Ref", render: (r) => `#${r.id}` },
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
                <Text>
                  {r.start_date} → {r.end_date}
                  <Text span c="dimmed" size="xs">
                    {" "}· {r.days_requested} d
                  </Text>
                </Text>
              ),
            },
            {
              key: "recommendation",
              header: "Unit Head",
              render: (r) => (
                <Badge
                  variant="dot"
                  color={
                    r.recommendation === "recommended" ? "green" : "orange"
                  }
                >
                  {r.recommendation
                    ? r.recommendation.replace(/_/g, " ")
                    : "—"}
                </Badge>
              ),
            },
            {
              key: "act",
              header: "",
              align: "right",
              render: (r) => (
                <Button size="xs" variant="light"
                  onClick={() => setTarget(r)}>
                  Decide
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
          ? `Sanction request #${target.id}`
          : ""}
      >
        <Stack>
          {target && (
            <>
              <Text size="sm">
                <strong>{CATEGORY_LABELS[target.category]}</strong>{" "}
                · {target.start_date} → {target.end_date} ·{" "}
                {target.days_requested} day
                {target.days_requested === 1 ? "" : "s"}
              </Text>
              <Text size="sm" c="dimmed">
                {target.purpose || "No purpose given."}
              </Text>
              <Text size="xs" c="dimmed">
                Unit Head recommendation:{" "}
                {target.recommendation
                  ? target.recommendation.replace(/_/g, " ")
                  : "not recorded"}
              </Text>
            </>
          )}

          <Group>
            <Button
              variant={outcome === "approve" ? "filled" : "default"}
              color="green"
              onClick={() => setOutcome("approve")}
            >
              Approve
            </Button>
            <Button
              variant={outcome === "reject" ? "filled" : "default"}
              color="red"
              onClick={() => setOutcome("reject")}
            >
              Reject
            </Button>
          </Group>

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
              loading={sanction.isPending}
              onClick={submit}
            >
              Record decision
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}