import { useState, useEffect } from 'react';
import { candidatesAPI } from '../services/api';
import { Users, Plus, Search, Mail, Phone, MapPin, Briefcase, X, Upload, ExternalLink } from 'lucide-react';

const Candidates = () => {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => { loadCandidates(); }, []);

  const loadCandidates = async () => {
    try {
      setLoading(true);
      const params = searchTerm ? { search: searchTerm } : {};
      const response = await candidatesAPI.getAll(params);
      setCandidates(response.data);
    } catch (error) {
      console.error('Failed to load candidates:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => { e.preventDefault(); loadCandidates(); };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Candidates</h1>
          <p className="text-slate-500 mt-1">Manage your talent pool</p>
        </div>
        <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Add Candidate
        </button>
      </div>

      <div className="card p-4">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input type="text" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search by name, email, skills..." className="input pl-12" />
          </div>
          <button type="submit" className="btn btn-secondary">Search</button>
        </form>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="spinner"></div></div>
      ) : candidates.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {candidates.map((candidate) => (
            <div key={candidate.id} className="card hover:shadow-lg transition-all">
              <div className="card-body">
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white text-xl font-semibold">
                    {candidate.full_name?.charAt(0)?.toUpperCase() || '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-slate-900 truncate">{candidate.full_name}</h3>
                    <p className="text-sm text-slate-500 truncate">{candidate.email}</p>
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  {candidate.phone && (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Phone className="w-4 h-4" /> {candidate.phone}
                    </div>
                  )}
                  {candidate.location && (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <MapPin className="w-4 h-4" /> {candidate.location}
                    </div>
                  )}
                  {candidate.experience_years && (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Briefcase className="w-4 h-4" /> {candidate.experience_years} years experience
                    </div>
                  )}
                </div>
                {candidate.skills && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {candidate.skills.split(',').slice(0, 4).map((skill, i) => (
                      <span key={i} className="badge badge-primary">{skill.trim()}</span>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100">
                  <button className="btn btn-secondary flex-1 py-2">View Profile</button>
                  {candidate.linkedin_url && (
                    <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" className="btn btn-ghost py-2">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <Users className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-xl font-semibold text-slate-900 mb-2">No candidates found</h3>
          <p className="text-slate-500 mb-6">Add candidates to start building your talent pool</p>
          <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
            <Plus className="w-4 h-4" /> Add Candidate
          </button>
        </div>
      )}

      {showCreateModal && <CreateCandidateModal onClose={() => setShowCreateModal(false)} onSuccess={() => { setShowCreateModal(false); loadCandidates(); }} />}
    </div>
  );
};

const CreateCandidateModal = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({ email: '', full_name: '', phone: '', location: '', linkedin_url: '', skills: '', experience_years: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = { ...formData, experience_years: formData.experience_years ? parseFloat(formData.experience_years) : null };
      await candidatesAPI.create(data);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add candidate');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden animate-in">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">Add New Candidate</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {error && <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">{error}</div>}
          <div className="space-y-5">
            <div>
              <label className="label">Full Name *</label>
              <input type="text" name="full_name" value={formData.full_name} onChange={handleChange} className="input" required />
            </div>
            <div>
              <label className="label">Email *</label>
              <input type="email" name="email" value={formData.email} onChange={handleChange} className="input" required />
            </div>
            <div>
              <label className="label">Phone</label>
              <input type="tel" name="phone" value={formData.phone} onChange={handleChange} className="input" />
            </div>
            <div>
              <label className="label">Location</label>
              <input type="text" name="location" value={formData.location} onChange={handleChange} className="input" />
            </div>
            <div>
              <label className="label">Years of Experience</label>
              <input type="number" step="0.5" name="experience_years" value={formData.experience_years} onChange={handleChange} className="input" />
            </div>
            <div>
              <label className="label">LinkedIn URL</label>
              <input type="url" name="linkedin_url" value={formData.linkedin_url} onChange={handleChange} className="input" />
            </div>
            <div>
              <label className="label">Skills (comma-separated)</label>
              <input type="text" name="skills" value={formData.skills} onChange={handleChange} className="input" placeholder="e.g., Python, React, AWS" />
            </div>
          </div>
          <div className="flex items-center gap-3 mt-6 pt-6 border-t border-slate-100">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">{loading ? 'Adding...' : 'Add Candidate'}</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Candidates;
