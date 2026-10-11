import { useState } from "react";
import {
  Badge, Button, Card, Container, Group, Modal, Stack, Text, Textarea,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { FaCalendarAlt, FaTrash } from "react-icons/fa";

import { useAuth } from "../../../auth/AuthProvider";
import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { StatusBadge } from "../../../ui/components/StatusBadge";
import {
  useMyApplications, useRequestCancellation, useWithdraw,
} from "../api/hooks";
import {
  CATEGORY_LABELS, PENDING_STATUSES,
  type LeaveApplication,
} from "../api/types";

function period(a: LeaveApplication): string {
  if (a.start_date === a.end_date) {
    return a.half_day
      ? `${a.start_date} (${a.half_day} half)`
      : a.start_date;
  }
  return `${a.start_date} → ${a.end_date}`;
}

export default function MyLeavePage() {
  const { data, isPending, error } = useMyApplications();
  const withdraw = useWithdraw();
  const cancel = useRequestCancellation();
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState<LeaveApplication | null>(null);
  const [opened, { open, close }] = useDisclosure(false);
  const { can } = useAuth();

  const canCancel = can("elm.application.cancel_request");

  if (error) {
    return <Container size="xl"><ErrorState error={error} /></Container>;
  }

  function confirmCancel(a: LeaveApplication) {
    setTarget(a);
    setReason("");
    open();
  }

  function doWithdraw(a: LeaveApplication) {
    withdraw.mutate({ id: a.id, reason: "" }, {
      onSuccess: () =>
        notifications.show({
          message: "The request has been withdrawn.",
          color: "green" }),
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  function doCancel() {
    if (!target) return;
    cancel.mutate({ id: target.id, reason }, {
      onSuccess: () => {
        notifications.show({
          message: "Cancellation requested.",
          color: "green" });
        close();
      },
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  return (
    <Container size="xl">
      <PageHeader
        title="My Leave"
        subtitle="Your requests, their current state and any recorded decision"
      />

      <Card padding="lg">
        <DataTable<LeaveApplication>
          rows={data?.results ?? []}
          loading={isPending}
          rowKey={(r) => r.id}
          minWidth={980}
          empty={{
            icon: FaCalendarAlt,
            title: "No leave requests yet",
            description: "Apply for leave to see it tracked here.",
          }}
          columns={[
            {
              key: "category",
              header: "Category",
              render: (r) => (
                <Text fw={600}>{CATEGORY_LABELS[r.category]}</Text>
              ),
            },
            {
              key: "start_date",
              header: "Period",
              render: (r) => (
                <Stack gap={0}>
                  <Text>{period(r)}</Text>
                  <Text size="xs" c="dimmed">
                    {r.days_requested} day
                    {r.days_requested === 1 ? "" : "s"}
                  </Text>
                </Stack>
              ),
            },
            {
              key: "status",
              header: "Status",
              render: (r) => (
                <Group gap={4}>
                  <StatusBadge status={r.status} />
                  {r.station_leave && (
                    <Badge size="xs" variant="outline" color="grape">
                      Station leave
                    </Badge>
                  )}
                </Group>
              ),
            },
            {
              key: "decision",
              header: "Decision",
              render: (r) => (
                <Stack gap={0}>
                  {r.recommendation && (
                    <Text size="xs" c="dimmed">
                      Unit Head:{" "}
                      {r.recommendation.replace(/_/g, " ")}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed">
                    {r.decision_reason || "—"}
                  </Text>
                </Stack>
              ),
            },
            {
              key: "actions",
              header: "",
              align: "right",
              render: (r) => (
                <Group gap="xs" justify="flex-end">
                  {PENDING_STATUSES.includes(r.status) && (
                    <Button
                      size="xs"
                      variant="light"
                      color="red"
                      leftSection={<FaTrash size={10} />}
                      loading={withdraw.isPending}
                      onClick={() => doWithdraw(r)}
                    >
                      Withdraw
                    </Button>
                  )}
                  {canCancel
                    && r.status === "approved"
                    && new Date(r.start_date) > new Date()
                    && (
                    <Button
                      size="xs"
                      variant="light"
                      color="orange"
                      onClick={() => confirmCancel(r)}
                    >
                      Cancel
                    </Button>
                  )}
                </Group>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        opened={opened}
        onClose={close}
        title="Request cancellation"
      >
        <Stack>
          <Text size="sm" c="dimmed">
            Cancellation follows the same hierarchy as the original
            leave. The approved leave is not edited in place.
          </Text>
          <Textarea
            label="Reason"
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
            autosize
            minRows={3}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>Cancel</Button>
            <Button
              color="orange"
              loading={cancel.isPending}
              onClick={doCancel}
            >
              Request cancellation
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}