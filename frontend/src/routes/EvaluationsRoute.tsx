import { Box, Button, Flex, Grid, Spinner, Text } from '@chakra-ui/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { TriangleAlert } from 'lucide-react'

import { PageTitle, PanelHeader, Stat } from '../components/primitives'
import { getEvaluations, runAgentEvaluations } from '../lib/api'
import type { EvaluationComparison, EvaluationResult } from '../types/evaluation'

const POLICY_ORDER = ['no-op', 'always-replan', 'agent', 'oracle']
const POLICY_DETAILS: Record<string, { label: string; description: string }> = {
  'no-op': {
    label: 'Do nothing',
    description: 'Keeps the original schedule after disruptions',
  },
  'always-replan': {
    label: 'Always replan',
    description: 'Builds a new schedule after every disruption',
  },
  agent: {
    label: 'AI decides',
    description: 'Lets the AI agent decide when replanning is worthwhile',
  },
  oracle: {
    label: 'Best-case benchmark',
    description: 'Uses future knowledge as a comparison target',
  },
}

function policyDetails(name: string) {
  return POLICY_DETAILS[name] ?? {
    label: name.replaceAll('-', ' '),
    description: 'Custom evaluation strategy',
  }
}

function scenarioLabel(id: string) {
  return id
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

function money(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function controllableCost(result: EvaluationResult): number {
  const { metrics } = result
  return metrics.controllable_cost ?? metrics.total_cost
}

function optionalNumber(value: number | undefined): string {
  return value === undefined
    ? '—'
    : value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

/** Signed delta against the no-op run, which is the do-nothing control. */
function CostDelta({ result, control }: { result: EvaluationResult; control?: number }) {
  if (control === undefined || result.policy_name === 'no-op') {
    return <Text className="num-cell delta-flat">reference</Text>
  }
  const delta = controllableCost(result) - control
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
  const queryClient = useQueryClient()
  const evaluationQuery = useQuery({
    queryKey: ['evaluations'],
    queryFn: getEvaluations,
    // Deterministic by construction, so there is nothing to gain from refetching.
    staleTime: Infinity,
  })
  const agentEvaluation = useMutation({
    mutationFn: runAgentEvaluations,
    // Mutation state dies with the component, so leaving the run only in
    // agentEvaluation.data loses it the moment this route remounts — and an
    // agent run costs real model calls to repeat. Promoting it into the cache
    // keeps it for the rest of the session.
    onSuccess: (comparison) => {
      queryClient.setQueryData<EvaluationComparison>(['evaluations'], comparison)
    },
  })

  if (evaluationQuery.isPending) {
    return (
      <>
        <PageTitle
          title="Evaluations"
          sub="Comparing scheduling strategies across repeatable factory disruptions."
        />
        <Flex className="panel-loading">
          <Spinner size="sm" />
          <Text>Comparing strategies from the same starting factory state…</Text>
        </Flex>
      </>
    )
  }

  if (evaluationQuery.isError) {
    return (
      <>
        <PageTitle
          title="Evaluations"
          sub="Comparing scheduling strategies across repeatable factory disruptions."
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

  const { scenarios, results } = agentEvaluation.data ?? evaluationQuery.data
  const policyNames = POLICY_ORDER.filter((name) =>
    results.some((result) => result.policy_name === name),
  )
  const totalReplans = results.reduce((sum, result) => sum + result.metrics.replans, 0)
  const violations = results.reduce(
    (sum, result) => sum + result.metrics.constraint_violations,
    0,
  )

  return (
    <>
      <PageTitle
        title="Evaluations"
        sub="See whether changing the schedule after a disruption actually improves delivery cost."
      />

      <Flex gap="2" align="center" marginBottom="4">
        <Button
          size="sm"
          onClick={() => agentEvaluation.mutate()}
          loading={agentEvaluation.isPending}
        >
          Add AI agent comparison
        </Button>
        <Text className="evaluation-action-note">
          Optional · uses your configured AI model and may take a few minutes.
        </Text>
      </Flex>
      {agentEvaluation.isError && (
        <Box className="inline-error">
          Could not run the agent evaluation. {agentEvaluation.error.message}
        </Box>
      )}

      <Grid className="stat-strip">
        <Stat
          label="Scenarios"
          value={String(scenarios.length)}
          note={`${results.length} runs total`}
        />
        <Stat
          label="Strategies"
          value={String(policyNames.length)}
          note={policyNames.map((name) => policyDetails(name).label).join(', ')}
        />
        <Stat label="Schedule changes" value={String(totalReplans)} note="across all runs" />
        <Stat
          label="Invalid schedules"
          value={String(violations)}
          note={violations === 0 ? 'All schedules passed checks' : 'Needs investigation'}
        />
      </Grid>

      {scenarios.map((scenario) => {
        const rows = results
          .filter((result) => result.scenario_id === scenario.id)
          .toSorted(
            (a, b) =>
              POLICY_ORDER.indexOf(a.policy_name) -
              POLICY_ORDER.indexOf(b.policy_name),
          )
        const controlRow = rows.find((row) => row.policy_name === 'no-op')
        const control = controlRow ? controllableCost(controlRow) : undefined
        const best = Math.min(...rows.map(controllableCost))

        return (
          <section className="data-panel evaluation-panel" key={scenario.id}>
            <PanelHeader
              title={scenarioLabel(scenario.id)}
              meta={`${scenario.event_count} event${scenario.event_count === 1 ? '' : 's'} over ${scenario.horizon_hour} hours`}
            />
            <Box className="panel-note">{scenario.description}</Box>

            <Box className="table-header eval-columns">
              <Text>Strategy</Text>
              <Text>Late orders</Text>
              <Text>Units unfinished</Text>
              <Text>Scheduling cost</Text>
              <Text>vs do nothing</Text>
              <Text>Plan changes</Text>
              <Text>Invalid plans</Text>
            </Box>
            {rows.map((row) => {
              const policy = policyDetails(row.policy_name)
              return (
                <Grid className="table-row eval-columns" key={row.policy_name}>
                  <Box title={`Run ID: ${row.final_state_hash}`}>
                    <Text className="primary-cell">{policy.label}</Text>
                    <Text className="strategy-description">
                      {policy.description}
                      {row.policy_name === 'agent'
                        ? ` · ${row.metrics.model_calls} AI call${row.metrics.model_calls === 1 ? '' : 's'}`
                        : ''}
                    </Text>
                  </Box>
                  <Text className="num-cell">{row.metrics.late_orders}</Text>
                  <Text className="num-cell">
                    {optionalNumber(row.metrics.unmet_demand_units)}
                  </Text>
                  <Text
                    className={`num-cell${
                      controllableCost(row) === best ? ' cost-best' : ''
                    }`}
                    title={`late orders ${money(row.metrics.penalty_cost)} · overtime ${money(
                      row.metrics.overtime_cost ?? 0,
                    )} · changeovers ${money(row.metrics.changeover_cost ?? 0)}`}
                  >
                    {money(controllableCost(row))}
                  </Text>
                  <CostDelta result={row} control={control} />
                  <Text className="num-cell">{row.metrics.replans}</Text>
                  <Text
                    className={`num-cell${row.metrics.constraint_violations > 0 ? ' delta-worse' : ''}`}
                  >
                    {row.metrics.constraint_violations}
                  </Text>
                </Grid>
              )
            })}
          </section>
        )
      })}

      <Flex className="evaluation-footnote">
        <TriangleAlert size={13} />
        <Text>
          Scheduling cost includes late-order penalties, overtime, and line changeovers.
          Production cost is left out because it does not measure schedule quality.
          Repeatable strategies use the same starting state; AI results may vary. To
          regenerate the comparison data, run{' '}
          <code>python -m backend.evaluation</code>.
        </Text>
      </Flex>
    </>
  )
}
