import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''
const MAIN_API = import.meta.env.VITE_MAIN_API_URL || ''

const DOMAIN_EMOJI = {
  frontend: '🎨',
  backend: '⚙️',
  fullstack: '🔧',
  ios: '📱',
  android: '📱',
  devops: '🚀',
  data: '📊',
  ml: '🤖',
  design: '✏️',
  product: '📋',
  default: '💼',
}

export default function Demo() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [readyJobs, setReadyJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        // Fetch published jobs from main backend
        const { data } = await axios.get(`${MAIN_API}/api/public/jobs?skip=0&limit=50`)
        setJobs(data)

        // Check which ones are ready in the interview module
        const statuses = await Promise.all(
          data.map(job =>
            axios.get(`${API}/api/interview/job/${job.id}/setup/status`)
              .then(r => ({ id: job.id, status: r.data.status }))
              .catch(() => ({ id: job.id, status: 'unknown' }))
          )
        )

        const readyIds = new Set(statuses.filter(s => s.status === 'ready').map(s => s.id))
        setReadyJobs(data.filter(j => readyIds.has(j.id)))
      } catch (e) {
        setError('Could not load jobs. Make sure TalentBridge is running.')
      } finally {
        setLoading(false)
      }
    }

    fetchJobs()
  }, [])

  const startInterview = async (job) => {
    setStarting(job.id)
    setError('')
    try {
      const { data } = await axios.post(`${API}/api/interview/session`, {
        job_id: job.id,
        job_description: job.description || job.title,
        resume_text: 'Demo candidate',
        difficulty: 3,
        seniority_bar: job.experience_level || 'senior',
        time_limit: 45,
        num_questions: 6,
        behavioral_pct: 20,
      })
      navigate(`/interview/${data.session_id}`)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start interview. Please try again.')
      setStarting(null)
    }
  }

  const getEmoji = (job) => {
    const title = (job.title || '').toLowerCase()
    if (title.includes('front')) return DOMAIN_EMOJI.frontend
    if (title.includes('back')) return DOMAIN_EMOJI.backend
    if (title.includes('full')) return DOMAIN_EMOJI.fullstack
    if (title.includes('ios')) return DOMAIN_EMOJI.ios
    if (title.includes('android')) return DOMAIN_EMOJI.android
    if (title.includes('devops') || title.includes('infra')) return DOMAIN_EMOJI.devops
    if (title.includes('data') || title.includes('analyst')) return DOMAIN_EMOJI.data
    if (title.includes('ml') || title.includes('machine') || title.includes('ai')) return DOMAIN_EMOJI.ml
    if (title.includes('design')) return DOMAIN_EMOJI.design
    if (title.includes('product') || title.includes('manager')) return DOMAIN_EMOJI.product
    return DOMAIN_EMOJI.default
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'flex-start',
      padding: '48px 24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <div style={{ fontSize: '3rem', marginBottom: '12px' }}>🤖</div>
        <h1 style={{ color: '#fff', fontSize: '2rem', fontWeight: '700', margin: '0 0 8px' }}>
          TalentBridge AI Interview
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: '1rem', margin: 0 }}>
          Select a role to start a mock AI-powered interview
        </p>
      </div>

      {/* Content */}
      <div style={{ width: '100%', maxWidth: '720px' }}>
        {loading && (
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.8)', fontSize: '1rem' }}>
            Loading available interviews...
          </div>
        )}

        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.15)',
            border: '1px solid rgba(239,68,68,0.4)',
            borderRadius: '12px',
            padding: '16px',
            color: '#fecaca',
            textAlign: 'center',
            marginBottom: '24px',
          }}>
            {error}
          </div>
        )}

        {!loading && readyJobs.length === 0 && !error && (
          <div style={{
            background: 'rgba(255,255,255,0.1)',
            borderRadius: '16px',
            padding: '32px',
            textAlign: 'center',
            color: 'rgba(255,255,255,0.8)',
          }}>
            <div style={{ fontSize: '2rem', marginBottom: '12px' }}>⚙️</div>
            <p style={{ margin: 0 }}>No interviews are ready yet. Publish jobs and wait for question generation to complete.</p>
          </div>
        )}

        {readyJobs.map(job => (
          <button
            key={job.id}
            onClick={() => startInterview(job)}
            disabled={starting === job.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              width: '100%',
              background: starting === job.id ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.95)',
              border: 'none',
              borderRadius: '16px',
              padding: '20px 24px',
              marginBottom: '16px',
              cursor: starting === job.id ? 'not-allowed' : 'pointer',
              textAlign: 'left',
              transition: 'transform 0.15s, box-shadow 0.15s',
              boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
            }}
            onMouseEnter={e => {
              if (starting !== job.id) {
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 8px 30px rgba(0,0,0,0.2)'
              }
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,0,0,0.15)'
            }}
          >
            <div style={{ fontSize: '2rem', marginRight: '16px', flexShrink: 0 }}>
              {getEmoji(job)}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: '700', fontSize: '1rem', color: '#1e293b', marginBottom: '4px' }}>
                {job.title}
              </div>
              <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
                {job.department}{job.location ? ` · ${job.location}` : ''}
                {job.experience_level ? ` · ${job.experience_level.charAt(0).toUpperCase() + job.experience_level.slice(1)}` : ''}
              </div>
            </div>
            <div style={{ flexShrink: 0, marginLeft: '16px' }}>
              {starting === job.id ? (
                <div style={{
                  width: '24px', height: '24px', border: '3px solid #e2e8f0',
                  borderTop: '3px solid #667eea', borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }} />
              ) : (
                <div style={{
                  background: 'linear-gradient(135deg, #667eea, #764ba2)',
                  color: '#fff',
                  borderRadius: '8px',
                  padding: '8px 16px',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                }}>
                  Start →
                </div>
              )}
            </div>
          </button>
        ))}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
