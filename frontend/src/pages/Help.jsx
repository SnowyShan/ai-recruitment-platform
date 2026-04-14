import React, { useState } from 'react';
import { supportAPI } from '../services/api';
import { 
  LifeBuoy, 
  Send, 
  MessageSquare, 
  AlertCircle, 
  BookOpen, 
  CheckCircle2,
  Clock,
  HelpCircle,
  Lightbulb,
  ShieldCheck
} from 'lucide-react';

const Help = () => {
  const [formData, setFormData] = useState({
    subject: '',
    category: 'technical',
    priority: 'medium',
    message: ''
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await supportAPI.create(formData);
      setSuccess(true);
      setFormData({
        subject: '',
        category: 'technical',
        priority: 'medium',
        message: ''
      });
      // Reset success message after 5 seconds
      setTimeout(() => setSuccess(false), 5000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const faqs = [
    {
      question: "How do I invite candidates to screening?",
      answer: "You can invite candidates by going to the Applications page, selecting the candidates you want to screen, and clicking 'Invite to Screening'."
    },
    {
      question: "Can I customize the screening questions?",
      answer: "Yes, you can manage the question bank in the Settings or specify job-specific questions during job creation."
    },
    {
      question: "How does the AI match score work?",
      answer: "Our AI analyzes the candidate's resume against the job requirements, experience, and skills to provide a percentage match score."
    }
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Header section with gradient background */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary-600 to-accent-600 p-8 md:p-12 text-white shadow-xl">
        <div className="relative z-10 space-y-4 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-xs font-semibold uppercase tracking-wider">
            <LifeBuoy className="w-3 h-3" />
            Support Center
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight">How can we help you today?</h1>
          <p className="text-primary-100 text-lg md:text-xl font-light">
            Whether you're facing a technical issue or have a genius feature request, our team is here to support you.
          </p>
        </div>
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 rounded-full bg-white/10 blur-3xl"></div>
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 rounded-full bg-accent-400/20 blur-3xl"></div>
        <HelpCircle className="absolute top-1/2 right-12 w-32 h-32 text-white/5 -translate-y-1/2" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Contact Form */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card shadow-lg border-slate-200/50">
            <div className="card-header flex items-center gap-3 bg-slate-50/50">
              <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center text-primary-600">
                <Send className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Submit a Request</h2>
                <p className="text-xs text-slate-500 font-normal">We'll get back to you within 24 hours.</p>
              </div>
            </div>
            <div className="card-body">
              {success ? (
                <div className="flex flex-col items-center justify-center py-12 text-center space-y-4 animate-in">
                  <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 mb-2">
                    <CheckCircle2 className="w-10 h-10" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900">Request Sent Successfully!</h3>
                  <p className="text-slate-500 max-w-sm mx-auto">
                    Your request has been received. Our support team will review it and get back to you shortly.
                  </p>
                  <button 
                    onClick={() => setSuccess(false)}
                    className="btn btn-secondary mt-4"
                  >
                    Submit Another Request
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                  {error && (
                    <div className="p-4 rounded-xl bg-red-50 border border-red-100 flex items-center gap-3 text-red-700 text-sm animate-in">
                      <AlertCircle className="w-5 h-5 flex-shrink-0" />
                      {error}
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-1.5">
                      <label htmlFor="category" className="label">Category</label>
                      <select
                        id="category"
                        name="category"
                        value={formData.category}
                        onChange={handleChange}
                        className="input appearance-none bg-no-repeat bg-right pr-10"
                        style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2364748b'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`, backgroundSize: '1.25rem' }}
                      >
                        <option value="technical">Technical Support</option>
                        <option value="billing">Billing Inquiry</option>
                        <option value="feature_request">Feature Request</option>
                        <option value="bug">Report a Bug</option>
                        <option value="other">General Question</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <label htmlFor="priority" className="label">Priority</label>
                      <select
                        id="priority"
                        name="priority"
                        value={formData.priority}
                        onChange={handleChange}
                        className="input appearance-none bg-no-repeat bg-right pr-10"
                        style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2364748b'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`, backgroundSize: '1.25rem' }}
                      >
                        <option value="low">Low - General inquiry</option>
                        <option value="medium">Medium - Normal request</option>
                        <option value="high">High - Urgent issue</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="subject" className="label">Subject</label>
                    <input
                      type="text"
                      id="subject"
                      name="subject"
                      value={formData.subject}
                      onChange={handleChange}
                      placeholder="e.g., Cannot invite candidate to screening"
                      required
                      className="input"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="message" className="label">Detailed Message</label>
                    <textarea
                      id="message"
                      name="message"
                      value={formData.message}
                      onChange={handleChange}
                      rows={6}
                      placeholder="Please describe your issue or request in detail..."
                      required
                      className="input py-3 resize-none"
                    ></textarea>
                    <p className="text-xs text-slate-400">
                      Include as much detail as possible to help us assist you faster.
                    </p>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="btn btn-primary w-full md:w-auto md:px-8 py-3 h-auto text-base"
                  >
                    {loading ? (
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                        Submitting...
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Send className="w-5 h-5" />
                        Send Request
                      </div>
                    )}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar content */}
        <div className="space-y-6">
          {/* Quick Stats/Links */}
          <div className="card p-6 bg-slate-900 text-white overflow-hidden relative">
            <h3 className="text-lg font-bold mb-4 relative z-10">System Status</h3>
            <div className="space-y-4 relative z-10">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">API Gateway</span>
                <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                  Operational
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">AI Engine</span>
                <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                  Operational
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Database</span>
                <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                  Operational
                </span>
              </div>
            </div>
            <div className="absolute -bottom-6 -right-6 w-24 h-24 bg-primary-600/20 rounded-full blur-2xl"></div>
          </div>

          {/* FAQ Preview */}
          <div className="card">
            <div className="card-header border-none pb-0">
              <h3 className="text-base font-bold flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-primary-500" />
                Common Questions
              </h3>
            </div>
            <div className="card-body space-y-6">
              {faqs.map((faq, index) => (
                <div key={index} className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-900 leading-tight">{faq.question}</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">{faq.answer}</p>
                </div>
              ))}
              <button className="btn btn-ghost w-full justify-start px-0 text-primary-600 hover:bg-transparent hover:text-primary-700 font-bold h-auto py-0">
                View All Documentation →
              </button>
            </div>
          </div>

          {/* Resources */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 rounded-2xl bg-primary-50 border border-primary-100 hover:bg-primary-100 transition-colors cursor-pointer group">
              <Lightbulb className="w-5 h-5 text-primary-600 mb-2 group-hover:scale-110 transition-transform" />
              <div className="text-xs font-bold text-slate-900">Guides</div>
            </div>
            <div className="p-4 rounded-2xl bg-accent-50 border border-accent-100 hover:bg-accent-100 transition-colors cursor-pointer group">
              <ShieldCheck className="w-5 h-5 text-accent-600 mb-2 group-hover:scale-110 transition-transform" />
              <div className="text-xs font-bold text-slate-900">Privacy</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Help;
