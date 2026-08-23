import { Box, Button, Flex, Grid, Heading, Spinner, Text } from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import { Check, Sparkles, TriangleAlert, X } from 'lucide-react'

import { commitSchedule, optimizeFactory } from '../lib/api'
import type { FactoryState, ScheduleResult } from '../types/factory'

interface ScheduleDialogProps {
  factoryName: string
  state: FactoryState
  onClose: () => void
  onCommitted: (state: FactoryState) => void
}

export function ScheduleDialog({ factoryName, state, onClose, onCommitted }: ScheduleDialogProps) {
  const optimize = useMutation({ mutationFn: () => optimizeFactory(factoryName) })
  const commit = useMutation({
    mutationFn: (result: ScheduleResult) =>
      commitSchedule(factoryName, state.schedule_version, result.jobs),
    onSuccess: ({ state: committedState }) => onCommitted(committedState),
  })
  const result = optimize.data
  const valid = result?.validation?.violations.length === 0
  const complete = result?.status === 'optimal' || result?.status === 'feasible'
  const committable = Boolean(result && valid && complete)
  const totalCost = result
    ? result.cost.late_penalty + result.cost.overtime + result.cost.changeover
    : 0

  return (
    <Flex className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <Box className="schedule-dialog" role="dialog" aria-modal="true" aria-labelledby="schedule-title" onMouseDown={(event) => event.stopPropagation()}>
        <Flex className="dialog-header">
          <Box>
            <Text className="eyebrow">Decision preview</Text>
            <Heading id="schedule-title" className="dialog-title">Build production schedule</Heading>
          </Box>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}><X size={16} /></Button>
        </Flex>

        {!result && !optimize.isPending && (
          <Box className="schedule-empty">
            <Sparkles size={22} />
            <Heading>Find a lower-cost plan</Heading>
            <Text>The optimizer assigns open orders across available lines. Nothing changes until you review and commit the result.</Text>
            <Button className="advance-button" onClick={() => optimize.mutate()}>Run optimizer</Button>
          </Box>
        )}

        {optimize.isPending && (
          <Flex className="schedule-loading"><Spinner size="sm" /><Text>Solving machine, inventory, and deadline constraints…</Text></Flex>
        )}

        {optimize.isError && <Flex className="form-error"><TriangleAlert size={14} /> {optimize.error.message}</Flex>}

        {result && (
          <>
            <Grid className="schedule-summary">
              <Summary label="Result" value={result.status.replace('_', ' ')} />
              <Summary label="Planned jobs" value={String(result.jobs.length)} />
              <Summary label="Estimated cost" value={`$${totalCost.toLocaleString()}`} />
              <Summary label="Solve time" value={`${result.solve_seconds.toFixed(2)}s`} />
            </Grid>

            <Box className="schedule-jobs">
              <Flex className="schedule-list-head"><Text>Proposed sequence</Text><Text>v{state.schedule_version + 1}</Text></Flex>
              {result.jobs.slice(0, 8).map((job) => (
                <Grid className="schedule-job" key={job.id}>
                  <Box><Text>{job.order_id}</Text><Text>{job.machine_id}</Text></Box>
                  <Text>{job.quantity} units</Text>
                  <Text>{job.start_hour.toFixed(1)}–{job.end_hour.toFixed(1)}h</Text>
                </Grid>
              ))}
              {result.jobs.length > 8 && <Text className="schedule-more">+{result.jobs.length - 8} more jobs</Text>}
            </Box>

            {result.unscheduled_orders.length > 0 && (
              <Text className="schedule-warning"><TriangleAlert size={13} /> {result.unscheduled_orders.length} orders could not be scheduled. This partial plan cannot be committed.</Text>
            )}
            {result.validation && result.validation.violations.length > 0 && (
              <Text className="schedule-warning"><TriangleAlert size={13} /> Validation found {result.validation.violations.length} violations.</Text>
            )}

            <Flex className="dialog-actions">
              <Button variant="outline" size="sm" onClick={() => optimize.mutate()} loading={optimize.isPending}>Run again</Button>
              <Button className="commit-button" size="sm" disabled={!committable} loading={commit.isPending} onClick={() => commit.mutate(result)}><Check size={14} /> Commit schedule</Button>
            </Flex>
            {commit.isError && <Flex className="form-error"><TriangleAlert size={14} /> {commit.error.message}</Flex>}
          </>
        )}
      </Box>
    </Flex>
  )
}

function Summary({ label, value }: { label: string; value: string }) {
  return <Box><Text className="eyebrow">{label}</Text><Text>{value}</Text></Box>
}
