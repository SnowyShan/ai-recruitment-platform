import { CheckCircle } from 'lucide-react'

export default function ThankYou() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="flex justify-center">
          <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center">
            <CheckCircle className="w-10 h-10 text-emerald-600" />
          </div>
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Interview Complete!</h1>
          <p className="text-slate-500 text-sm leading-relaxed">
            Thank you for completing the screening interview. Your responses have been submitted successfully.
            The recruiting team will review your interview and be in touch soon.
          </p>
        </div>
        <p className="text-xs text-slate-400">You can now close this window.</p>
      </div>
    </div>
  )
}
