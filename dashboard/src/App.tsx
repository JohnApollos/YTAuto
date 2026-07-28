import { useEffect, useState } from 'react'
import './index.css'

function App() {
  const [healthStatus, setHealthStatus] = useState<string>('checking...');

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/system/health')
      .then(res => res.json())
      .then(data => setHealthStatus(data.status))
      .catch(err => setHealthStatus(`error: ${err.message}`));
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-900 text-white font-sans">
      <div className="max-w-2xl text-center space-y-8 p-10 bg-gray-800 rounded-3xl shadow-2xl border border-gray-700">
        <div className="space-y-4">
          <h1 className="text-5xl font-extrabold tracking-tight bg-gradient-to-r from-brand-500 to-purple-400 bg-clip-text text-transparent">
            Autonomous Media
          </h1>
          <p className="text-xl text-gray-400">
            System Control Dashboard
          </p>
        </div>

        <div className="flex items-center justify-center space-x-3 p-4 bg-gray-900 rounded-xl border border-gray-700 inline-flex">
          <div className="flex items-center space-x-2">
            <span className="text-gray-400 font-medium">API Health:</span>
            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
              healthStatus === 'ok' 
                ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                : healthStatus === 'checking...'
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              {healthStatus}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-left mt-8">
          <div className="p-6 bg-gray-700/50 rounded-2xl border border-gray-600 hover:border-brand-500 transition-colors cursor-default">
            <h3 className="text-lg font-bold text-gray-200">Channels</h3>
            <p className="text-sm text-gray-400 mt-2">Manage properties and quotas</p>
          </div>
          <div className="p-6 bg-gray-700/50 rounded-2xl border border-gray-600 hover:border-brand-500 transition-colors cursor-default">
            <h3 className="text-lg font-bold text-gray-200">Pipelines</h3>
            <p className="text-sm text-gray-400 mt-2">Monitor active inference jobs</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
