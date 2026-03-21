import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

const VIDEO_PROVIDERS = [
  {
    value: 'did',
    label: 'D-ID',
    description: 'Basic lip-sync avatar. Fast, low cost. Close-up face only.',
  },
  {
    value: 'heygen',
    label: 'HeyGen',
    description: 'Higher quality, natural gestures, half-body framing. Recommended.',
  },
  {
    value: 'mock',
    label: 'Mock (disabled)',
    description: 'No video generated. Audio-only interview.',
  },
]

export default function Settings() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [originalPrompt, setOriginalPrompt] = useState('')
  const [videoProvider, setVideoProvider] = useState('did')
  const [originalVideoProvider, setOriginalVideoProvider] = useState('did')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    axios.get(`${API}/api/interview/settings`).then(({ data }) => {
      setPrompt(data.evaluation_prompt || '')
      setOriginalPrompt(data.evaluation_prompt || '')
      setVideoProvider(data.video_provider || 'did')
      setOriginalVideoProvider(data.video_provider || 'did')
      setLoading(false)
    })
  }, [])

  const save = async () => {
    setSaving(true)
    await axios.put(`${API}/api/interview/settings`, {
      evaluation_prompt: prompt,
      video_provider: videoProvider,
    })
    setOriginalPrompt(prompt)
    setOriginalVideoProvider(videoProvider)
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const isDirty = prompt !== originalPrompt || videoProvider !== originalVideoProvider

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-6">
      <div className="max-w-2xl mx-auto animate-fade-in">

        <div className="flex items-center gap-4 mb-8">
          <button onClick={() => navigate('/')} className="btn btn-secondary text-sm px-3 py-1.5">
            ← Back
          </button>
          <h1 className="text-xl font-bold text-slate-900">Interview Settings</h1>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="spinner" />
          </div>
        ) : (
          <div className="space-y-6">

            {/* Video Provider */}
            <div className="card p-6 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-800 mb-1">Video Provider</h2>
                <p className="text-slate-500 text-sm mb-4">
                  Controls which service generates the recruiter avatar video for Video Interview mode.
                  Changing this affects new jobs — existing videos are not regenerated.
                </p>
                <div className="space-y-3">
                  {VIDEO_PROVIDERS.map(p => (
                    <label
                      key={p.value}
                      className={`flex items-start gap-3 p-3 rounded-xl border-2 cursor-pointer transition-colors ${
                        videoProvider === p.value
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <input
                        type="radio"
                        name="video_provider"
                        value={p.value}
                        checked={videoProvider === p.value}
                        onChange={() => setVideoProvider(p.value)}
                        className="mt-0.5 accent-indigo-600"
                      />
                      <div>
                        <span className="text-sm font-medium text-slate-800">{p.label}</span>
                        <p className="text-xs text-slate-500 mt-0.5">{p.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* Evaluation Guidelines */}
            <div className="card p-6 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-800 mb-1">Evaluation Guidelines</h2>
                <p className="text-slate-500 text-sm mb-4">
                  These instructions guide the AI when scoring candidate answers. Changes apply to future interviews only —
                  modifying this mid-cycle may create inconsistent evaluations across candidates for the same role.
                </p>

                {prompt !== originalPrompt && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4 text-amber-700 text-sm">
                    ⚠️ Unsaved changes will affect all future interview evaluations. Ensure open roles have finished interviewing before saving.
                  </div>
                )}

                <textarea
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  rows={14}
                  className="input resize-none font-mono text-xs"
                />
              </div>
            </div>

            {/* Save */}
            <div className="flex items-center justify-between">
              <button
                onClick={() => { setPrompt(originalPrompt); setVideoProvider(originalVideoProvider); }}
                disabled={!isDirty}
                className="text-sm text-slate-400 hover:text-slate-600 disabled:opacity-30 transition-colors"
              >
                Discard changes
              </button>
              <button
                onClick={save}
                disabled={saving || !isDirty}
                className="btn btn-primary"
              >
                {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Changes'}
              </button>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
