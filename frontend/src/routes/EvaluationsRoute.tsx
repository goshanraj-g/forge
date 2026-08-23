import { Box, Button, Flex, Grid, Spinner, Text } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { TriangleAlert } from 'lucide-react'

import { PageTitle, PanelHeader, Stat } from '../components/primitives'
import { getEvaluations } from '../lib/api'
import type { EvaluationResult } from '../types/evaluation'

const BASELINE_ORDER = ['no-op', 'always-replan', 'oracle']

function money(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

/** Signed delta against the no-op run, which is the do-nothing control. */
function CostDelta({ result, control }: { result: EvaluationResult; control?: number }) {
  if (control === undefined || result.policy_name === 'no-op') {
    return <Text className="num-cell delta-flat">baseline</Text>
  }
  const delta = result.metrics.controllable_cost - control
  if (Math.abs(delta) < 0.5) {
    return <Text className="num-cell delta-flat">no change</Text>
  }
  return (
    <Text className={`num-cell ${delta < 0 ? 'delta-better' : 'delta-worse'}`}>
      {delta < 0 ? '−' : '+'}
      {money(Math.abs(delta)).slice(1)}
    </Text>
  )
}

export function EvaluationsRoute() {
  const evaluationQuery = useQuery({
    queryKey: ['evaluations'],
    queryFn: getEvaluations,
    // Deterministic by construction, so there is nothing to gain from refetching.
    staleTime: Infinity,
  })

  if (evaluationQuery.isPending) {
    return (
      <>
        <PageTitle
          title="Evaluations"
          sub="Replaying every scenario against every baseline policy."
        />
        <Flex className="panel-loading">
          <Spinner size="sm" />
          <Text>Running scenarios from clean initial states…</Text>
        </Flex>
      </>
    )
  }

  if (evaluationQuery.isError) {
    return (
      <>
        <PageTitle
          title="Evaluations"
          sub="Replaying every scenario against every baseline policy."
        />
        <Box className="inline-error">
          Could not run the evaluation harness. {evaluationQuery.error.message}
        </Box>
        <Button size="sm" onClick={() => void evaluationQuery.refetch()}>
          Try again
        </Button>
      </>
    )
  }

  const { scenarios, results } = evaluationQuery.data
  const totalReplans = results.reduce((sum, result) => sum + result.metrics.replans, 0)
  const violations = results.reduce(
    (sum, result) => sum + result.metrics.constraint_violations,
    0,
  )

  return (
    <>
      <PageTitle
        title="Evaluations"
        sub="Does replanning actually help? Each scenario replays from a clean initial state against three fixed policies."
      />

      <Grid className="stat-strip">
        <Stat
          label="Scenarios"
          value={String(scenarios.length)}
          note={`${results.length} runs total`}
        />
        <Stat label="Policies" value="3" note="no-op, always-replan, oracle" />
        <Stat label="Replans issued" value={String(totalReplans)} note="across all runs" />
        <Stat
          label="Constraint violations"
          value={String(violations)}
          note={violations === 0 ? 'every schedule validated' : 'needs investigation'}
        />
      </Grid>

      {scenarios.map((scenario) => {
        const rows = results
          .filter((result) => result.scenario_id === scenario.id)
          .toSorted(
            (a, b) =>
              BASELINE_ORDER.indexOf(a.policy_name) -
              BASELINE_ORDER.indexOf(b.policy_name),
          )
        const control = rows.find((row) => row.policy_name === 'no-op')?.metrics
          .controllable_cost
        const best = Math.min(...rows.map((row) => row.metrics.controllable_cost))

        return (
          <section className="data-panel evaluation-panel" key={scenario.id}>
            <PanelHeader
              title={scenario.id}
              meta={`${scenario.event_count} event${scenario.event_count === 1 ? '' : 's'} · ${scenario.horizon_hour}h horizon`}
            />
            <Box className="panel-note">{scenario.description}</Box>

            <Box className="table-header eval-columns">
              <Text>Policy</Text>
              <Text>Late orders</Text>
              <Text>Unmet units</Text>
              <Text>Controllable cost</Text>
              <Text>vs no-op</Text>
              <Text>Replans</Text>
              <Text>Violations</Text>
            </Box>
            {rows.map((row) => (
              <Grid className="table-row eval-columns" key={row.policy_name}>
                <Box>
                  <Text className="primary-cell">{row.policy_name}</Text>
                  <Text className="sub-cell">{row.final_state_hash.slice(0, 12)}</Text>
                </Box>
                <Text className="num-cell">{row.metrics.late_orders}</Text>
                <Text className="num-cell">
                  {row.metrics.unmet_demand_units.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </Text>
                <Text
                  className={`num-cell${
                    row.metrics.controllable_cost === best ? ' cost-best' : ''
                  }`}
                  title={`penalty ${money(row.metrics.penalty_cost)} · overtime ${money(
                    row.metrics.overtime_cost,
                  )} · changeover ${money(row.metrics.changeover_cost)}`}
                >
                  {money(row.metrics.controllable_cost)}
                </Text>
                <CostDelta result={row} control={control} />
                <Text className="num-cell">{row.metrics.replans}</Text>
                <Text
                  className={`num-cell${row.metrics.constraint_violations > 0 ? ' delta-worse' : ''}`}
                >
                  {row.metrics.constraint_violations}
                </Text>
              </Grid>
            ))}
          </section>
        )
      })}

      <Flex className="evaluation-footnote">
        <TriangleAlert size={13} />
        <Text>
          Policies are ranked on controllable cost — late penalty plus overtime plus
          changeover. Cost of goods is excluded because it follows demand, not
          scheduling, so counting it would reward a run that simply builds less.
          Scenarios are hashed and replayed from fixed initial states, so these numbers
          reproduce exactly between runs. Regenerate from the CLI with{' '}
          <code>python -m backend.evaluation</code>.
        </Text>
      </Flex>
    </>
  )
}
