import { Container } from "@mantine/core";
import { FaBell } from "react-icons/fa";

import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useNotifications } from "../api/hooks";
import type { ElmNotification } from "../api/types";

export default function NotificationsPage() {
  const { data, isPending, error } = useNotifications();

  if (error) {
    return <Container size="xl"><ErrorState error={error} /></Container>;
  }

  return (
    <Container size="xl">
      <PageHeader
        title="Notifications"
        subtitle="Task assignments, recorded decisions and SLA reminders"
      />
      <Container size="xl" px={0}>
        <DataTable<ElmNotification>
          rows={data?.results ?? []}
          loading={isPending}
          rowKey={(r) => r.id}
          minWidth={760}
          empty={{
            icon: FaBell,
            title: "Nothing to read",
            description:
              "You are notified when a task is assigned to you and when a decision is recorded.",
          }}
          columns={[
            {
              key: "subject",
              header: "Subject",
              render: (r) => (
                <div>
                  <div style={{ fontWeight: 600 }}>{r.subject}</div>
                  <div
                    style={{
                      fontSize: 12, opacity: 0.7, whiteSpace: "normal",
                    }}
                  >
                    {r.body}
                  </div>
                </div>
              ),
            },
            {
              key: "topic",
              header: "Kind",
              render: (r) => r.topic.replace(/\./g, " "),
            },
            {
              key: "created_at",
              header: "When",
              render: (r) =>
                new Date(r.created_at).toLocaleString(),
            },
          ]}
        />
      </Container>
    </Container>
  );
}