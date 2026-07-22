import test from 'node:test'
import assert from 'node:assert/strict'

import { roundToQuarterHour } from '../src/timeRounding.js'

test('rounds durations to the nearest 15 minutes', () => {
  assert.equal(roundToQuarterHour(67), 60)
  assert.equal(roundToQuarterHour(68), 75)
  assert.equal(roundToQuarterHour(83), 90)
})

test('rounds exact halfway ties up', () => {
  assert.equal(roundToQuarterHour(67.5), 75)
})

test('leaves quarter-hour durations unchanged', () => {
  assert.equal(roundToQuarterHour(0), 0)
  assert.equal(roundToQuarterHour(15), 15)
  assert.equal(roundToQuarterHour(60), 60)
})

test('keeps a short positive duration as one submittable quarter hour', () => {
  assert.equal(roundToQuarterHour(7), 15)
})

test('rejects invalid and oversized durations', () => {
  assert.equal(roundToQuarterHour('not-a-number'), 0)
  assert.equal(roundToQuarterHour('1e1000'), 0)
  assert.equal(roundToQuarterHour(1440), 1440)
  assert.equal(roundToQuarterHour(1441), 0)
})
