import { Box, Button, Flex, Heading, Spinner, Text } from '@chakra-ui/react'
import { ArrowRight, BrainCircuit, TriangleAlert, X } from 'lucide-react'

import type { AgentDecisionRecord, FactoryEvent } from '../types/factory'

interface DecisionDialogProps {
  event: FactoryEvent
  result?: AgentDecisionRecord
  loading: boolean
  error?: Error
  onClose: () => void
  onReplan: () => void
  onRetry: () => void
}

export function DecisionDialog({ event, result, loading, error, onClose, onReplan, onRetry }: DecisionDialogProps) {
  const decision = result?.decision

  return (
    <Flex className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <Box className="decision-dialog" role="dialog" aria-modal="true" aria-labelledby="decision-title" onMouseDown={(click) => click.stopPropagation()}>
        <Flex className="dialog-header">
          <Box>
            <Text className="eyebrow"><BrainCircuit size={13} /> Agent investigation</Text>
            <Heading id="decision-title" className="dialog-title">Event {event.id}</Heading>
          </Box>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}><X size={16} /></Button>
        </Flex>

        {loading && <Flex className="decision-loading"><Spinner size="sm" /><Text>Inspecting factory state and current commitments…</Text></Flex>}
        {error && (
          <Box className="decision-failed">
            <Flex className="form-error"><TriangleAlert size={14} /> {error.message}</Flex>
            <Button size="sm" variant="outline" onClick={onRetry}>Run investigation again</Button>
          </Box>
        )}

        {decision && (
          <>
            <Flex className="decision-verdict">
              <span className={`severity severity-${decision.severity}`}>{decision.severity}</span>
              <Text>{decision.status.replaceAll('_', ' ')}</Text>
            </Flex>
            <Heading className="decision-summary">{decision.summary}</Heading>
            <Text className="decision-explanation">{decision.explanation}</Text>

            <Box className="decision-evidence">
              <DecisionList label="Affected orders" values={decision.affected_order_ids} empty="None identified" />
              <DecisionList label="Affected machines" values={decision.affected_machine_ids} empty="None identified" />
              {decision.missing_information.length > 0 && <DecisionList label="Missing information" values={decision.missing_information} empty="None" />}
            </Box>

            <Flex className="decision-meta">
              <Text>Snapshot {result.state_snapshot_hash.slice(0, 10)}</Text>
              <Text>Schedule v{result.schedule_version}</Text>
              <Text>Hour {result.simulation_hour.toFixed(2)}</Text>
            </Flex>

            <Flex className="dialog-actions">
              <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
              {decision.should_replan && <Button className="commit-button" size="sm" onClick={onReplan}>Review new plan <ArrowRight size={14} /></Button>}
            </Flex>
          </>
        )}
      </Box>
    </Flex>
  )
}

function DecisionList({ label, values, empty }: { label: string; values: string[]; empty: string }) {
  return <Box><Text className="eyebrow">{label}</Text><Text>{values.length ? values.join(', ') : empty}</Text></Box>
}
