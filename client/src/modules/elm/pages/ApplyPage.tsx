import { useState } from "react";
import {
  Button, Card, Checkbox, Container, Group, NativeSelect,
  Stack, Text, Textarea, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaPaperPlane } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useApply, useEmployees, useMyApplications, useNominateReplacement,
} from "../api/hooks";
import { CATEGORY_LABELS, type LeaveCategory } from "../api/types";

const CATEGORY_HINTS: Record<LeaveCategory, string> = {
  CL: "8 days a year. First- or second-half days are supported.",
  RH: "2 days a year, only on a published Restricted Holiday.",
  SCL: "Up to 15 days a year; admissibility is the authority's call.",
  EL: "Earned Leave, counted continuously. Carries forward.",
  COL: "20 days a year, balance- and evidence-controlled.",
  VL: "Faculty only, during a published vacation period.",
};

export default function ApplyPage() {
  const employees = useEmployees();
  const mine = useMyApplications();
  const apply = useApply();
  const replace = useNominateReplacement();

  const [category, setCategory] =
    useState<LeaveCategory>("CL");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [halfDay, setHalfDay] = useState("");
  const [purpose, setPurpose] = useState("");
  const [stationLeave, setStationLeave] = useState(false);
  const [stationDetails, setStationDetails] = useState("");
  const [substituteRequired, setSubstituteRequired] =
    useState(false);
  const [substituteId, setSubstituteId] = useState<string>("");
  const [declinedId, setDeclinedId] = useState<string>("");
  const [replacementId, setReplacementId] = useState<string>("");

  if (employees.error) {
    return (
      <Container size="xl">
        <ErrorState error={employees.error} />
      </Container>
    );
  }

  function doSubmit() {
    apply.mutate({
      category,
      start_date: start,
      end_date: end || start,
      half_day: halfDay,
      purpose,
      station_leave: stationLeave,
      station_leave_details: stationLeave ? stationDetails : "",
      substitute_required: substituteRequired,
      substitute_user_id: substituteRequired
        ? Number(substituteId) : null,
    }, {
      onSuccess: () => {
        notifications.show({
          message: "Leave application submitted.",
          color: "green" });
        setStart("");
        setEnd("");
        setPurpose("");
        setStationDetails("");
      },
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  function doReplace() {
    replace.mutate({
      id: Number(declinedId),
      substitute_user_id: Number(replacementId),
    }, {
      onSuccess: () => {
        notifications.show({
          message: "Replacement substitute nominated.",
          color: "green" });
        setDeclinedId("");
        setReplacementId("");
      },
      onError: (e) =>
        notifications.show({
          message: errorMessage(e), color: "red" }),
    });
  }

  const employeeOptions = [
    { value: "", label: "Select a substitute" },
    ...(employees.data?.results ?? []).map((e) => ({
      value: String(e.user_id),
      label: `#${e.user_id} ${e.designation}`,
    })),
  ];

  /** Only a request whose substitute declined is replaceable. */
  const declinedOptions = (mine.data?.results ?? [])
    .filter((a) => a.status === "applicant_action_required")
    .map((a) => ({
      value: String(a.id),
      label: `#${a.id} ${a.category} ${a.start_date}`,
    }));

  return (
    <Container size="md">
      <PageHeader
        title="Apply for Leave"
        subtitle="One application per leave. Station leave is captured inside the same application."
      />

      <Card padding="lg">
        <Stack>
          <NativeSelect
            label="Leave category"
            data={Object.entries(CATEGORY_LABELS).map(
              ([value, label]) => ({ value, label }))}
            value={category}
            onChange={(e) =>
              setCategory(e.currentTarget.value as LeaveCategory)}
          />
          <Text size="xs" c="dimmed">
            {CATEGORY_HINTS[category]}
          </Text>

          <Group grow>
            <TextInput
              type="date"
              label="From"
              value={start}
              onChange={(e) =>
                setStart(e.currentTarget.value)}
            />
            <TextInput
              type="date"
              label="To"
              description="Leave the same as From for a single day."
              value={end}
              onChange={(e) =>
                setEnd(e.currentTarget.value)}
            />
          </Group>

          {category === "CL" && (
            <NativeSelect
              label="Half day"
              data={[
                { value: "", label: "Full day" },
                { value: "first", label: "First half (0.5 day)" },
                { value: "second", label: "Second half (0.5 day)" },
              ]}
              value={halfDay}
              onChange={(e) => setHalfDay(e.currentTarget.value)}
            />
          )}

          <Textarea
            label="Purpose"
            value={purpose}
            onChange={(e) => setPurpose(e.currentTarget.value)}
            autosize
            minRows={2}
          />

          <Checkbox
            label="I will be outside Jabalpur (Station Leave)"
            checked={stationLeave}
            onChange={(e) =>
              setStationLeave(e.currentTarget.checked)}
          />
          {stationLeave && (
            <Textarea
              label="Station leave details"
              value={stationDetails}
              onChange={(e) =>
                setStationDetails(e.currentTarget.value)}
              autosize
              minRows={2}
            />
          )}

          <Checkbox
            label="A substitute is required for this period"
            checked={substituteRequired}
            onChange={(e) =>
              setSubstituteRequired(e.currentTarget.checked)}
          />
          {substituteRequired && (
            <NativeSelect
              label="Substitute"
              data={employeeOptions}
              value={substituteId}
              onChange={(e) =>
                setSubstituteId(e.currentTarget.value)}
            />
          )}

          <Button
            leftSection={<FaPaperPlane size={12} />}
            loading={apply.isPending}
            onClick={doSubmit}
            disabled={!start}
          >
            Submit application
          </Button>
        </Stack>
      </Card>

      <Card padding="lg" mt="lg">
        <Stack>
          <Text fw={600}>
            Your substitute declined — nominate a replacement
          </Text>
          <Text size="sm" c="dimmed">
            The consent gate stays closed until a replacement accepts.
            You may also withdraw the request from My Leave.
          </Text>
          <Group grow>
            <NativeSelect
              label="Declined request"
              data={[
                { value: "", label: "Select a request" },
                ...declinedOptions,
              ]}
              value={declinedId}
              onChange={(e) =>
                setDeclinedId(e.currentTarget.value)}
            />
            <NativeSelect
              label="Replacement"
              data={employeeOptions}
              value={replacementId}
              onChange={(e) =>
                setReplacementId(e.currentTarget.value)}
            />
          </Group>
          <Button
            variant="light"
            loading={replace.isPending}
            disabled={!declinedId || !replacementId}
            onClick={doReplace}
          >
            Nominate replacement
          </Button>
        </Stack>
      </Card>
    </Container>
  );
}