import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import { TriangleAlert, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { scheduleMachineFailure } from '../lib/api'
import type { EventScheduledResponse, Machine } from '../types/factory'

interface IncidentDialogProps {
  factoryName: string
  machines: Machine[]
  currentHour: number
  onClose: () => void
  onScheduled: (result: EventScheduledResponse) => void
}

export function IncidentDialog({
  factoryName,
  machines,
  currentHour,
  onClose,
  onScheduled,
}: IncidentDialogProps) {
  const [machineId, setMachineId] = useState(machines[0]?.id ?? '')
  const [startHour, setStartHour] = useState(currentHour + 0.25)
  const [durationHours, setDurationHours] = useState(2)
  const mutation = useMutation({
    mutationFn: () =>
      scheduleMachineFailure(factoryName, {
        machineId,
        simHour: startHour,
        durationHours,
      }),
    onSuccess: onScheduled,
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <Flex className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <Box
        as="section"
        className="incident-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="incident-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <Flex className="dialog-header">
          <Box>
            <Text className="eyebrow">Simulation event</Text>
            <Heading id="incident-title" className="dialog-title">
              Inject machine failure
            </Heading>
          </Box>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </Button>
        </Flex>

        <Text className="dialog-copy">
          Schedule a temporary line outage. It takes effect when the simulation
          reaches the selected hour.
        </Text>

        <form onSubmit={submit}>
          <label className="field">
            <span>Production line</span>
            <select value={machineId} onChange={(event) => setMachineId(event.target.value)}>
              {machines.map((machine) => (
                <option value={machine.id} key={machine.id}>
                  {machine.name} ({machine.id})
                </option>
              ))}
            </select>
          </label>

          <div className="field-grid">
            <label className="field">
              <span>Starts at hour</span>
              <input type="number" min={currentHour} step="0.25" value={startHour} onChange={(event) => setStartHour(event.target.valueAsNumber)} required />
            </label>
            <label className="field">
              <span>Duration (hours)</span>
              <input type="number" min="0.25" step="0.25" value={durationHours} onChange={(event) => setDurationHours(event.target.valueAsNumber)} required />
            </label>
          </div>

          {mutation.isError && (
            <Flex className="form-error">
              <TriangleAlert size={14} /> {mutation.error.message}
            </Flex>
          )}

          <Flex className="dialog-actions">
            <Button variant="outline" size="sm" type="button" onClick={onClose}>Cancel</Button>
            <Button className="danger-button" size="sm" type="submit" loading={mutation.isPending}>Schedule failure</Button>
          </Flex>
        </form>
      </Box>
    </Flex>
  )
}
