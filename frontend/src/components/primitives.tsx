import { Box, Flex, Heading, Text } from '@chakra-ui/react'

import type { MachineStatus } from '../types/factory'

export function PageTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <Box className="title-row">
      <Heading className="page-title">{title}</Heading>
      <Text className="page-sub">{sub}</Text>
    </Box>
  )
}

export function StatusLight({ status }: { status: MachineStatus }) {
  return (
    <span className={`status status-${status}`}>
      <i aria-hidden="true" />
      {status}
    </span>
  )
}

export function Stat({
  label,
  value,
  note,
}: {
  label: string
  value: string
  note: string
}) {
  return (
    <Box className="stat">
      <Text className="eyebrow">{label}</Text>
      <Text className="stat-value">{value}</Text>
      <Text className="stat-note">{note}</Text>
    </Box>
  )
}

export function PanelHeader({ title, meta }: { title: string; meta: string }) {
  return (
    <Flex className="panel-header">
      <Heading className="panel-title">{title}</Heading>
      <Text className="eyebrow">{meta}</Text>
    </Flex>
  )
}
