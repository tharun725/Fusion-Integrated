import {
  Badge, Button, Card, Container, Table, Text, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCog } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useHierarchy, usePolicy, useSetHierarchyStep, useSetPolicy } from "../api/hooks";
import type { LeavePolicy } from "../api/types";

const ROLES = [
  { value: "unit_head", label: "Unit Head" },
  { value: "establishment", label: "Establishment (Dep. Reg. Estt.)" },
  { value: "deputy_registrar_estt", label: "Deputy Registrar (Estt.)" },
  { value: "dean", label: "Dean" },
  { value: "registrar", label: "Registrar" },
  { value: "director", label: "Director" },
];

export default function PolicyPage() {
  const policy = usePolicy();
  const hierarchy = useHierarchy();
  const setPolicy = useSetPolicy();
  const setStep = useSetHierarchyStep();

  if (policy.error || hierarchy.error) {
    return (
      <Container size="xl">
        <ErrorState error={policy.error ?? hierarchy.error!} />
      </Container>
    );
  }

  function save(key: string, value: string) {
    setPolicy.mutate({ key, value }, {
      onSuccess: () =>
        notifications.show({
          message: `${key} set to ${value}.`,
          color: "green" }),
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  function saveStep(body: Record<string, unknown>) {
    setStep.mutate(body, {
      onSuccess: () =>
        notifications.show({
          message: "Sanctioning step saved.",
          color: "green" }),
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  return (
    <Container size="xl">
      <PageHeader
        title="Policy & Hierarchy"
        subtitle="Current leave-policy parameters and the configured sanctioning path. There is no draft/publish lifecycle — the current value governs."
      />

      <Card padding="lg">
        <Text fw={600} mb="sm">
          Leave-policy parameters
        </Text>
        <DataTable<LeavePolicy>
          rows={policy.data?.results ?? []}
          loading={policy.isPending}
          rowKey={(r) => r.id}
          minWidth={700}
          empty={{
            icon: FaCog,
            title: "No parameters configured",
            description:
              "The module falls back to its built-in defaults until a parameter is set.",
          }}
          columns={[
            {
              key: "key",
              header: "Parameter",
              render: (r) => (
                <Text fw={600}>{r.key}</Text>
              ),
            },
            {
              key: "description",
              header: "Meaning",
              render: (r) => r.description || "—",
            },
            {
              key: "value",
              header: "Value",
              render: (r) => (
                <TextInput
                  defaultValue={r.value}
                  size="xs"
                  maw={160}
                  onBlur={(e) => {
                    const next = e.currentTarget.value;
                    if (next !== r.value) save(r.key, next);
                  }}
                />
              ),
            },
          ]}
        />
      </Card>

      <Card padding="lg" mt="lg">
        <Text fw={600} mb="xs">
          Sanctioning hierarchy
        </Text>
        <Text size="sm" c="dimmed" mb="sm">
          Steps are resolved in order. The last step is the final
          sanctioning authority. A step marked
          {" "}<Badge size="xs" variant="light">Establishment</Badge>
          {" "}is the optional processing step; removing it bypasses
          the step without creating a different outcome.
        </Text>

        <Table.ScrollContainer minWidth={680}>
          <Table verticalSpacing="sm" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Category</Table.Th>
                <Table.Th align="right">Order</Table.Th>
                <Table.Th>Role</Table.Th>
                <Table.Th>Establishment</Table.Th>
                <Table.Th align="right" />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(hierarchy.data?.results ?? []).map((h) => (
                <Table.Tr key={h.id}>
                  <Table.Td>
                    {h.category === "*" ? "All" : h.category}
                  </Table.Td>
                  <Table.Td align="right">{h.step_order}</Table.Td>
                  <Table.Td>
                    {ROLES.find((r) => r.value === h.role)?.label
                      ?? h.role}
                  </Table.Td>
                  <Table.Td>
                    {h.is_establishment
                      ? <Badge size="xs" color="indigo">Yes</Badge>
                      : "—"}
                  </Table.Td>
                  <Table.Td align="right">
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() => saveStep({
                        category: h.category,
                        step_order: h.step_order,
                        role: h.role,
                        is_establishment: false,
                      })}
                    >
                      Disable
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>
    </Container>
  );
}