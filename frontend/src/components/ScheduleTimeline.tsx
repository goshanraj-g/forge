import { Box, Flex, Grid, Heading, Text } from '@chakra-ui/react'

import type { FactoryState, Machine, ProductionJob } from '../types/factory'

const WINDOW_HOURS = 24
const TICKS = [0, 6, 12, 18, 24]

interface ScheduleTimelineProps {
  state: FactoryState
  machines: Machine[]
  onOptimize: () => void
}

export function ScheduleTimeline({ state, machines, onOptimize }: ScheduleTimelineProps) {
  const jobs = Object.values(state.jobs)
  const windowEnd = state.sim_hour + WINDOW_HOURS
  const visibleJobs = jobs.filter(
    (job) => job.end_hour > state.sim_hour && job.start_hour < windowEnd,
  )

  return (
    <section className="timeline-panel">
      <Flex className="timeline-header">
        <Box>
          <Text className="eyebrow">Current plan · v{state.schedule_version}</Text>
          <Heading className="panel-title">Production schedule</Heading>
        </Box>
        <button className="text-action" type="button" onClick={onOptimize}>
          {jobs.length ? 'Review plan options' : 'Create schedule'}
        </button>
      </Flex>

      {jobs.length === 0 ? (
        <Flex className="timeline-empty">
          <Box>
            <Text>No production plan has been committed.</Text>
            <Text>Create a schedule to assign open orders to production lines.</Text>
          </Box>
        </Flex>
      ) : (
        <Box className="timeline-body">
          <Grid className="timeline-scale-row">
            <Text>Line</Text>
            <Box className="timeline-scale">
              {TICKS.map((tick) => (
                <Text key={tick} style={{ left: `${(tick / WINDOW_HOURS) * 100}%` }}>
                  {tick === 0 ? 'Now' : `+${tick}h`}
                </Text>
              ))}
            </Box>
          </Grid>

          {machines.map((machine) => (
            <Grid className="timeline-row" key={machine.id}>
              <Box className="timeline-machine">
                <Text>{machine.name}</Text>
                <Text>{machine.id}</Text>
              </Box>
              <Box className="timeline-track">
                {TICKS.map((tick) => (
                  <i key={tick} style={{ left: `${(tick / WINDOW_HOURS) * 100}%` }} />
                ))}
                {visibleJobs
                  .filter((job) => job.machine_id === machine.id)
                  .map((job) => (
                    <JobBar job={job} currentHour={state.sim_hour} key={job.id} />
                  ))}
              </Box>
            </Grid>
          ))}
        </Box>
      )}
    </section>
  )
}

function JobBar({ job, currentHour }: { job: ProductionJob; currentHour: number }) {
  const visibleStart = Math.max(job.start_hour, currentHour)
  const visibleEnd = Math.min(job.end_hour, currentHour + WINDOW_HOURS)
  const left = ((visibleStart - currentHour) / WINDOW_HOURS) * 100
  const width = ((visibleEnd - visibleStart) / WINDOW_HOURS) * 100

  return (
    <Box
      className="job-bar"
      style={{ left: `${left}%`, width: `${Math.max(width, 1.2)}%` }}
      title={`${job.order_id}: ${job.quantity} units · ${job.start_hour.toFixed(1)}–${job.end_hour.toFixed(1)}h`}
    >
      <Text>{job.order_id}</Text>
    </Box>
  )
}
