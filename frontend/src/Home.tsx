import { fetchProposals, type Proposal } from './timesheet'

export default function Home() {
  return (
    <div className="card">
      <h2>Welcome</h2>
      <p>Use the <a href="/proposals">Proposals</a> page to generate, review, and approve time entries.</p>
    </div>
  )
}
