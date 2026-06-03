import React from "react";

export default function Links({ word }) {
  const hasSource = word?.source;
  const hasLinks = word?.external_links && Object.keys(word.external_links).length > 0;

  if (!hasSource && !hasLinks) return null;

  return (
    <div className="flex flex-col md:flex-row md:items-start md:justify-between pt-4 border-t border-gray-200">
      {/* Source */}
      {hasSource && (
        <section className="mb-3 md:mb-0 md:mr-6">
          <h4 className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-1">
            Source
          </h4>
          <p className="text-gray-700 font-medium">{word.source}</p>
        </section>
      )}

      {/* External Links */}
      {hasLinks && (
        <section className="flex-1">
          <h4 className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-1">
            External Links
          </h4>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {Object.entries(word.external_links).map(([name, url]) => (
              <a
                key={name}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              >
                {name.charAt(0).toUpperCase() + name.slice(1)} →
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
