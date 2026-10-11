import {
  Card, Container, Progress, Stack, Table, Text,
} from "@mantine/core";
import { FaBalanceScale } from "react-icons/fa";

import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useBalances, useTransactions } from "../api/hooks";
import { CATEGORY_LABELS, type LeaveBalance } from "../api/types";

/** How much of the granted entitlement has been consumed. */
function usedPct(b: LeaveBalance): number {
  const granted = b.entitled + b.opening;
  if (granted <= 0) return 0;
  return Math.min(100, Math.round((b.used / granted) * 100));
}

export default function BalancesPage() {
  const { data, isPending, error } = useBalances();
  const history = useTransactions();

  if (error) {
    return <Container size="xl"><ErrorState error={error} /></Container>;
  }

  const rows = data?.results ?? [];

  return (
    <Container size="xl">
      <PageHeader
        title="My Leave Balances"
        subtitle="Current entitlement, what has been used, and what carries forward"
      />

      <Card padding="lg">
        <DataTable<LeaveBalance>
          rows={rows}
          loading={isPending}
          rowKey={(r) => r.id}
          minWidth={820}
          empty={{
            icon: FaBalanceScale,
            title: "No balances yet",
            description:
              "Balances are created when you first apply for a leave category.",
          }}
          columns={[
            {
              key: "category",
              header: "Category",
              render: (r) => (
                <Stack gap={0}>
                  <Text fw={600}>{CATEGORY_LABELS[r.category]}</Text>
                  <Text size="xs" c="dimmed">{r.leave_year}</Text>
                </Stack>
              ),
            },
            {
              key: "entitled",
              header: "Entitled",
              align: "right",
              render: (r) => `${r.entitled}`,
            },
            {
              key: "opening",
              header: "Carried in",
              align: "right",
              render: (r) => `${r.opening}`,
            },
            {
              key: "used",
              header: "Used",
              align: "right",
              render: (r) => `${r.used}`,
            },
            {
              key: "lapsed",
              header: "Lapsed",
              align: "right",
              render: (r) => `${r.lapsed}`,
            },
            {
              key: "available",
              header: "Available",
              render: (r) => (
                <Stack gap={4} maw={140}>
                  <Text fw={700}>{r.available}</Text>
                  <Progress
                    value={usedPct(r)}
                    size="sm"
                    color={r.available > 0 ? "blue" : "red"}
                  />
                </Stack>
              ),
            },
          ]}
        />
      </Card>

      <Card padding="lg" mt="lg">
        <Text fw={600} mb="sm">Leave account history</Text>
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="sm" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>When</Table.Th>
                <Table.Th>Category</Table.Th>
                <Table.Th>Entry</Table.Th>
                <Table.Th align="right">Days</Table.Th>
                <Table.Th>Note</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(history.data?.results ?? []).map((t) => (
                <Table.Tr key={t.id}>
                  <Table.Td>
                    {new Date(t.created_at).toLocaleDateString()}
                  </Table.Td>
                  <Table.Td>{t.category}</Table.Td>
                  <Table.Td>{t.kind.replace(/_/g, " ")}</Table.Td>
                  <Table.Td align="right">{t.amount}</Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">{t.note || "—"}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {!history.isPending && !history.data?.results.length && (
          <Text size="sm" c="dimmed" mt="sm">
            No account entries yet.
          </Text>
        )}
      </Card>
    </Container>
  );
}