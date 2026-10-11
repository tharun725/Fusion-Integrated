import {
  Badge, Button, Card, Container, Group, Stack, Table, Text, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCalendarDay, FaUpload } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useCalendars, useCreateCalendar, useHolidays, usePublishCalendar,
} from "../api/hooks";
import type { HolidayCalendar } from "../api/types";

export default function CalendarPage() {
  const calendars = useCalendars();
  const holidays = useHolidays();
  const create = useCreateCalendar();
  const publish = usePublishCalendar();

  if (calendars.error || holidays.error) {
    return (
      <Container size="xl">
        <ErrorState error={calendars.error ?? holidays.error!} />
      </Container>
    );
  }

  function doPublish(c: HolidayCalendar) {
    publish.mutate(c.id, {
      onSuccess: () =>
        notifications.show({
          message: `Published — ${c.year} is now the effective calendar.`,
          color: "green" }),
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  function doCreate() {
    create.mutate({ year: "", label: "", holidays: [] }, {
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  return (
    <Container size="xl">
      <PageHeader
        title="Holiday / RH Calendar"
        subtitle="Date and RH validation use the currently effective published calendar until a replacement is published."
        action={
          <Group>
            <Button
              variant="light"
              leftSection={<FaUpload size={12} />}
              loading={publish.isPending}
              onClick={doCreate}
            >
              New calendar
            </Button>
          </Group>
        }
      />

      <Card padding="lg">
        <Text fw={600} mb="sm">Calendars</Text>
        <DataTable<HolidayCalendar>
          rows={calendars.data?.results ?? []}
          loading={calendars.isPending}
          rowKey={(r) => r.id}
          minWidth={720}
          empty={{
            icon: FaCalendarDay,
            title: "No calendar yet",
            description:
              "Publish one before any RH or weekend-sensitive request is validated.",
          }}
          columns={[
            { key: "year", header: "Year" },
            { key: "label", header: "Label" },
            {
              key: "published",
              header: "State",
              render: (r) => (
                <Group gap={4}>
                  {r.is_published
                    ? <Badge size="sm" color="blue">Published</Badge>
                    : <Badge size="sm" color="gray">Draft</Badge>}
                  {r.is_effective && (
                    <Badge size="sm" color="green">Effective</Badge>
                  )}
                </Group>
              ),
            },
            {
              key: "published_at",
              header: "Published",
              render: (r) => r.published_at
                ? new Date(r.published_at).toLocaleString()
                : "—",
            },
            {
              key: "act",
              header: "",
              align: "right",
              render: (r) => (
                <Button
                  size="xs"
                  variant="light"
                  disabled={r.is_published}
                  loading={publish.isPending}
                  onClick={() => doPublish(r)}
                >
                  Publish
                </Button>
              ),
            },
          ]}
        />
      </Card>

      <Card padding="lg" mt="lg">
        <Text fw={600} mb="sm">
          Days on record
        </Text>
        <Stack gap="xs">
          <TextInput
            size="xs"
            placeholder="Filter by date (YYYY-MM-DD)"
            description="Leave blank to show every recorded day."
          />
        </Stack>
        <Table.ScrollContainer minWidth={620} mt="sm">
          <Table verticalSpacing="sm" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Date</Table.Th>
                <Table.Th>Label</Table.Th>
                <Table.Th>Restricted Holiday</Table.Th>
                <Table.Th>Institute closed</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(holidays.data?.results ?? []).map((h) => (
                <Table.Tr key={h.id}>
                  <Table.Td>{h.date}</Table.Td>
                  <Table.Td>{h.label}</Table.Td>
                  <Table.Td>
                    {h.is_restricted_holiday
                      ? <Badge size="xs" color="grape">RH</Badge>
                      : "—"}
                  </Table.Td>
                  <Table.Td>
                    {h.is_closed
                      ? <Badge size="xs" color="gray">Closed</Badge>
                      : "Open"}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {!holidays.isPending && !holidays.data?.results.length && (
          <Text size="sm" c="dimmed" mt="sm">
            No days recorded yet.
          </Text>
        )}
      </Card>
    </Container>
  );
}