export default function InterviewBriefing({ onStart, jobTitle }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg max-w-lg w-full p-8">
        <h1 className="text-2xl font-bold mb-2">Ready for your interview?</h1>
        {jobTitle && <p className="text-gray-500 mb-6">Position: <strong>{jobTitle}</strong></p>}

        <div className="mb-6">
          <h2 className="font-semibold mb-3">Before you begin:</h2>
          <ul className="space-y-2">
            {[
              "Find a quiet place with no background noise",
              "Make sure your microphone is working",
              "You'll have time to think before answering each question",
              "Answer as you would in a real interview — be specific, use examples",
              "The interview takes approximately 20–30 minutes",
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-green-500 mt-0.5">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-6 text-sm text-amber-800">
          ⚠️ This interview is monitored. Keep this tab open and stay in frame throughout.
        </div>

        <button
          onClick={onStart}
          className="w-full bg-indigo-600 text-white py-3 rounded-xl font-semibold hover:bg-indigo-700 transition"
        >
          Start Interview →
        </button>
      </div>
    </div>
  );
}
