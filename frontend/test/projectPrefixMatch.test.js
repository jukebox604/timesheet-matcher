import test from 'node:test'
import assert from 'node:assert/strict'
import { matchProjectPrefix } from '../src/projectPrefixMatch.js'

const projects = [
  { id: 956015, name: 'ASR | Application Managed Services' },
  { id: 966753, name: 'ASR | Dispatch Advice & Invoicing at Suffix Level' },
  { id: 390351, name: 'BKC | Application Managed Services' },
  { id: 502827, name: 'BROWN | Application Managed Services' },
  { id: 951450, name: '*HJ | ERP Transformation Project' },
  { id: 959090, name: 'HJ | Testing' },
  { id: 417162, name: 'DG | Internal Activities' },
]

test('prefers the unique managed-services project for an explicit ASR prefix', () => {
  const match = matchProjectPrefix('ASR: Migration of ARS invoices, credit notes, invoices.', projects)
  assert.equal(match?.projectId, 956015)
  assert.equal(match?.label, 'ASR')
})

test('specific project subtitle overrides the AMS default', () => {
  assert.equal(matchProjectPrefix('ASR: Dispatch Advice & Invoicing at Suffix Level', projects)?.projectId, 966753)
})

test('client full names and codes work without adding case-specific rules', () => {
  assert.equal(matchProjectPrefix('BKC: QMS project', projects)?.projectId, 390351)
  assert.equal(matchProjectPrefix('Brownells: Invoice work', projects)?.projectId, 502827)
  assert.equal(matchProjectPrefix('Berkshire Corp: QMS work', projects)?.projectId, 390351)
})

test('ambiguous client codes stay unselected until reviewed', () => {
  assert.deepEqual(matchProjectPrefix('HJ: General work', projects), { ambiguous: true, label: 'HJ' })
  assert.equal(matchProjectPrefix('HJ: Testing', projects)?.projectId, 959090)
})

test('does not infer client from arbitrary text or substrings', () => {
  assert.equal(matchProjectPrefix('Migration of ASR invoices', projects), null)
  assert.equal(matchProjectPrefix('ARS: Migration of invoices', projects), null)
  assert.equal(matchProjectPrefix('ASR: Migration of invoices', []), null)
  assert.equal(matchProjectPrefix('10:00 AM ASR meeting', projects), null)
})
