import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

export default function Settings() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [original, setOriginal] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    axios.get(`${API}/api/interview/settings`).then(({ data }) => {
      setPrompt(data.evaluation_prompt)
      setOriginal(data.evaluation_prompt)
      setLoading(false)
    })
  }, [])

  const save = async () => {
    setSaving(true)
    await axios.put(`${API}/api/interview/settings`, { evaluation_prompt: prompt })
    setOriginal(prompt)
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const isDirty = prompt !== original

  return (
    <div className="min-h-screen p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/')} className="text-gray-500 hover:text-gray-300 transition-colors text-sm">
          ← Back
        </button>
        <h1 className="text-2xl font-bold text-white">Interview Settings</h1>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 space-y-4">
          <div>
            <h2 className="text-white font-semibold mb-1">Evaluation Guidelines</h2>
            <p className="text-gray-400 text-sm mb-4">
              These instructions are sent to the AI when evaluating candidate answers. Changes apply to future interviews only —
              modifying this mid-hiring-cycle may create inconsistent evaluations across candidates for the same role.
            </p>

            {isDirty && (
              <div className="bg-yellow-900 border border-yellow-700 rounded-xl px-4 py-3 mb-4 text-yellow-300 text-sm">
                ⚠️ You have unsaved changes. This will affect all future interview evaluations. Make sure any open job roles have finished interviewing before saving.
              </div>
            )}

            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              rows={14}
              className="w-full bg-gray-800 text-gray-200 text-sm rounded-xl p-4 border border-gray-700 focus:border-blue-500 focus:outline-none resize-none font-mono"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setPrompt(original)}
              disabled={!isDirty}
              className="text-sm text-gray-500 hover:text-gray-300 disabled:opacity-30 transition-colors"
            >
              Discard changes
            </button>
            <button
              onClick={save}
              disabled={saving || !isDirty}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 text-white font-semibold rounded-xl transition-colors text-sm"
            >
              {saving ? 'Saving...' : saved ? '✓ Saved' : 'Save Changes'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
