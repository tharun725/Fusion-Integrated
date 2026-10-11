import { useState } from "react";
import {
  Alert, Button, Card, Container, Group, Stack, Table, Text, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaChartBar } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useRunSla, useRunYearEnd, useSlaThresholds,
} from "../api/hooks";
import type { YearEndSummary } from "../api/types";

export default function ReportsPage() {
  const thresholds = useSlaThresholds();
  const runSla = useRunSla();
  const runYearEnd = useRunYearEnd();

  const [leaveYear, setLeaveYear] = useState(
    String(new Date().getFullYear() - 1));
  const [yearEnd, setYearEnd] = useState<YearEndSummary | null>(null);

  function doYearEnd() {
    runYearEnd.mutate(leaveYear, {
      onSuccess: (result) => {
        setYearEnd(result);
        notifications.show({
          message:
            `Processed ${result.accounts} account(s).`,
          color: result.exceptions.length ? "orange" : "green",
        });
      },
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  function doSla() {
    runSla.mutate(undefined, {
      onSuccess: (result) =>
        notifications.show({
          message:
            `${(result as { reminders: number }).reminders} reminder(s), `
            + `${(result as { escalations: number }).escalations} escalation(s) issued.`,
          color: "green" }),
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  const rows = Object.entries(
    thresholds.data ?? {},
  ).map(([taskClass, cfg]) => {
    const c = cfg as { reminder?: number; escalation?: number };
    return {
      task_class: taskClass,
      reminder: c.reminder ?? 0,
      escalation: c.escalation ?? 0,
    };
  });

  return (
    <Container size="lg">
      <PageHeader
        title="Reports & Event Processing"
        subtitle="Configured SLA thresholds, and the two event-triggered operations ELM performs"
      />

      <Card padding="lg">
        <Text fw={600} mb="sm">
          SLA thresholds (hours)
        </Text>
        <Text size="sm" c="dimmed" mb="sm">
          A reminder or escalation is issued only while the task is
          still pending; a completed task is never reminded or
          escalated.
        </Text>
        <Table.ScrollContainer minWidth={520}>
          <Table verticalSpacing="sm" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Task class</Table.Th>
                <Table.Th align="right">Reminder</Table.Th>
                <Table.Th align="right">Escalation</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r) => (
                <Table.Tr key={r.task_class}>
                  <Table.Td>{r.task_class.replace(/_/g, " ")}</Table.Td>
                  <Table.Td align="right">{r.reminder}</Table.Td>
                  <Table.Td align="right">{r.escalation}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        <Group mt="md">
          <Button
            variant="light"
            leftSection={<FaChartBar size={12} />}
            loading={runSla.isPending}
            onClick={doSla}
          >
            Run SLA processing now
          </Button>
        </Group>
      </Card>

      <Card padding="lg" mt="lg">
        <Text fw={600} mb="xs">
          Year-end processing
        </Text>
        <Text size="sm" c="dimmed" mb="sm">
          Unused CL, RH and SCL lapse; unused faculty VL converts to EL
          at 2:1 including fractions; EL and COL carry forward. The
          year-end boundary is an event trigger, not an ELM actor.
        </Text>
        <Group align="flex-end">
          <TextInput
            label="Leaving year"
            value={leaveYear}
            onChange={(e) =>
              setLeaveYear(e.currentTarget.value)}
            maw={140}
          />
          <Button
            color="orange"
            loading={runYearEnd.isPending}
            onClick={doYearEnd}
          >
            Execute year-end
          </Button>
        </Group>

        {yearEnd && (
          <Stack mt="md" gap="xs">
            <Table.ScrollContainer minWidth={480}>
              <Table verticalSpacing="xs" withTableBorder>
                <Table.Tbody>
                  <Table.Tr>
                    <Table.Td>Accounts processed</Table.Td>
                    <Table.Td align="right">{yearEnd.accounts}</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td>Days lapsed (CL/RH/SCL)</Table.Td>
                    <Table.Td align="right">
                      {yearEnd.lapsed_days}
                    </Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td>VL converted to EL (days)</Table.Td>
                    <Table.Td align="right">
                      {yearEnd.converted_vl_days}
                    </Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td>Days carried forward</Table.Td>
                    <Table.Td align="right">
                      {yearEnd.carried_forward_days}
                    </Table.Td>
                  </Table.Tr>
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {yearEnd.exceptions.length > 0 && (
              <Alert color="orange" title="Processing exceptions">
                <Stack gap={2}>
                  {yearEnd.exceptions.map((e) => (
                    <Text size="xs" key={e}>{e}</Text>
                  ))}
                </Stack>
              </Alert>
            )}
          </Stack>
        )}
      </Card>
    </Container>
  );
}