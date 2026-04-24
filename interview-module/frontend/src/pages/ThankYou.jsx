import { CheckCircle } from 'lucide-react'

export default function ThankYou({ candidateName }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg max-w-md w-full p-10 text-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-8 h-8 text-green-600" />
        </div>
        <h1 className="text-2xl font-bold mb-2">Interview Complete</h1>
        {candidateName && <p className="text-gray-500 mb-4">Thank you, {candidateName}.</p>}
        <p className="text-gray-600 mb-6">
          Your responses have been submitted for review. The hiring team will be in touch regarding next steps.
        </p>
        <p className="text-sm text-gray-400">You can close this window.</p>
      </div>
    </div>
  )
}
