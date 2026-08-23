import { Box, Button, Flex, Text } from '@chakra-ui/react'
import { Activity, Sparkles, TriangleAlert } from 'lucide-react'

import type { FactoryEvent } from '../types/factory'

interface ActivityLogProps {
  events: FactoryEvent[]
  investigatedIds: Set<string>
  onInjectFailure: () => void
  onOptimize: () => void
  onInvestigate: (event: FactoryEvent) => void
}

export function ActivityLog({ events, investigatedIds, onInjectFailure, onOptimize, onInvestigate }: ActivityLogProps) {
  return (
    <section className="activity-panel">
      <Flex className="activity-head">
        <Box>
          <Text className="eyebrow"><Activity size={13} /> Operations log</Text>
          <Text className="activity-summary">
            {events.length ? `${events.length} events recorded this session` : 'No events recorded yet'}
          </Text>
        </Box>
        <Flex gap="2">
          <Button size="sm" variant="outline" onClick={onInjectFailure}><TriangleAlert size={14} /> Add test failure</Button>
          <Button size="sm" className="optimize-button" onClick={onOptimize}><Sparkles size={14} /> Review schedule</Button>
        </Flex>
      </Flex>

      {events.length > 0 && (
        <Box className="activity-list">
          {events.slice(0, 6).map((event, index) => {
            const detail = describeEvent(event)
            return (
              <GridRow
                key={`${event.id}-${event.sim_hour}-${index}`}
                hour={event.sim_hour}
                title={detail.title}
                detail={detail.detail}
                tone={detail.tone}
                investigated={investigatedIds.has(event.id)}
                onInvestigate={() => onInvestigate(event)}
              />
            )
          })}
        </Box>
      )}
    </section>
  )
}

function GridRow({ hour, title, detail, tone, investigated, onInvestigate }: { hour: number; title: string; detail: string; tone: string; investigated: boolean; onInvestigate: () => void }) {
  return (
    <Flex className="activity-row">
      <Text className="activity-hour">H{hour.toFixed(2)}</Text>
      <i className={`activity-dot ${tone}`} aria-hidden="true" />
      <Box><Text>{title}</Text><Text>{detail}</Text></Box>
      <button
        className={`investigate-action${investigated ? ' investigated' : ''}`}
        type="button"
        onClick={onInvestigate}
      >
        {investigated ? 'View review' : 'Review impact'}
      </button>
    </Flex>
  )
}

function describeEvent(event: FactoryEvent): { title: string; detail: string; tone: string } {
  switch (event.type) {
    case 'machine_failure':
      return { title: 'Machine failure started', detail: `${value(event, 'machine_id')} · ${value(event, 'duration_hours')}h outage`, tone: 'danger' }
    case 'machine_repair':
      return { title: 'Machine returned to service', detail: value(event, 'machine_id'), tone: 'success' }
    case 'supplier_delay':
      return { title: 'Supplier delay reported', detail: `${value(event, 'shipment_id')} · ${value(event, 'delay_hours')}h delay`, tone: 'warning' }
    case 'urgent_order':
      return { title: 'Urgent order received', detail: `${value(event, 'product_id')} · ${value(event, 'quantity')} units`, tone: 'warning' }
    case 'low_inventory':
      return { title: 'Inventory below reorder point', detail: `${value(event, 'component_id')} · ${value(event, 'on_hand')} remaining`, tone: 'warning' }
    case 'shipment_received':
      return { title: 'Shipment received', detail: `${value(event, 'component_id')} · ${value(event, 'quantity')} units`, tone: 'success' }
    case 'order_complete':
      return { title: 'Order completed', detail: `${value(event, 'order_id')} · ${value(event, 'hours_late')}h late`, tone: 'success' }
    case 'order_late':
      return { title: 'Order missed its deadline', detail: value(event, 'order_id'), tone: 'danger' }
    default:
      return { title: event.type.replaceAll('_', ' '), detail: event.id, tone: 'neutral' }
  }
}

function value(event: FactoryEvent, key: string): string {
  const result = event[key]
  return typeof result === 'string' || typeof result === 'number' ? String(result) : 'Unknown'
}
