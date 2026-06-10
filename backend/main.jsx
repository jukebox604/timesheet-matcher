import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function useApi(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(path)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`${path} failed: ${response.status}`);
        }
        return response.json();
      })
      .then(setData)
      .catch((err) => setError(err.message));
  }, [path]);

  return { data, error };
}

function App() {
  const health = useApi('/api/health');
  const teamwork = useApi('/api/teamwork/status');

  const backendReady = health.data?.status === 'ok';
  const teamworkConnected = teamwork.data?.connected === true;
  const teamworkConfigured = teamwork.data?.configured === true;

  return (
    <main className="page-shell">
      <section className="hero-card">
        <div className="eyebrow">
          <span className={backendReady ? 'status-dot ready' : 'status-dot'} />
          Read-only Teamwork checkpoint
        </div>
        <h1>Timesheet Matcher</h1>
        <p className="lede">
          FastAPI is serving this React app from the Hostinger-managed
          <strong> timesheet</strong> container. The next layer is a safe,
          read-only Teamwork connection check — no writes, no timesheet changes.
        </p>

        <div className="status-grid">
          <article>
            <span>Frontend</span>
            <strong>React static build</strong>
          </article>
          <article>
            <span>Backend</span>
            <strong>{backendReady ? 'Connected' : health.error ? 'Offline' : 'Checking…'}</strong>
          </article>
          <article>
            <span>Teamwork</span>
            <strong>
              {teamworkConnected
                ? 'Connected'
                : teamworkConfigured
                  ? 'Configured, checking failed'
                  : teamwork.error
                    ? 'Status unavailable'
                    : 'Credentials needed'}
            </strong>
          </article>
        </div>

        <section className="connection-panel">
          <div>
            <span className="panel-label">Teamwork site</span>
            <strong>{teamwork.data?.site || 'doppiogroup.teamwork.com'}</strong>
          </div>
          <div>
            <span className="panel-label">Marc user ID</span>
            <strong>{teamwork.data?.user_id || '531538'}</strong>
          </div>
          <div>
            <span className="panel-label">Current mode</span>
            <strong>{teamwork.data?.auth_mode || 'No API secret loaded'}</strong>
          </div>
        </section>

        <pre className="health-box">
{JSON.stringify({
  backend: health.data || health.error || 'Checking backend health…',
  teamwork: teamwork.data || teamwork.error || 'Checking Teamwork status…',
}, null, 2)}
        </pre>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
