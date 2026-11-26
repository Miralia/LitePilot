import { describe, expect, it } from 'vitest'

import type { ScheduleInfo } from '@/api/types'
import { getSchedulerVisual } from '@/utils/schedulerVisual'

describe('scheduler visual rules', () => {
  it('matches the wallpaper scheduler by its corrected job id', () => {
    const visual = getSchedulerVisual({ id: 'random_wallpaper' } as ScheduleInfo)

    expect(visual.icon).toBe('mdi-image-outline')
  })
})
