import React from "react";

export default function Examples({ word }) {
  if (!word?.examples || word.examples.length === 0) {
    return null;
  }

  return (
    <section className="bg-blue-50 rounded-2xl p-6 pt-4">
      
      <div className="space-y-4">
        {word.examples.map((ex, i) => (
          <div key={i} className="bg-white rounded-lg p-4 border-l-4 border-blue-400">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              {ex.style && (
                <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-1 rounded-full">
                  {ex.style}
                </span>
              )}
              {ex.tags && ex.tags.length > 0 && (
                ex.tags.map((tag, idx) => (
                  <span key={idx} className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded-full">
                    {tag}
                  </span>
                ))
              )}
            </div>
            <p className="text-gray-800 leading-relaxed">{ex.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
