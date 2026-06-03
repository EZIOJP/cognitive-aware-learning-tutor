import React from 'react';

/**
 * Props:
 *  - word: {
 *      meaning, etymology, story_mnemonic, group_number, word_breakdown:{prefix,root,suffix}, category
 *    }
 *  - accentColor?: string (e.g., dominantColor) — optional
 */
export default function InfoGrid({ word, accentColor = 'var(--accent, #4f46e5)' }) {
  if (!word) return null;

  const safe = (v) => (v === null || v === undefined ? '' : v);

  const items = [
    { label: 'Meaning', value: safe(word.meaning), icon: '📖' },
    { label: 'Etymology', value: safe(word.etymology), icon: '🏛️' },
    { label: 'Story Mnemonic', value: safe(word.story_mnemonic), icon: '🧠' },
    {
      label: 'Word Breakdown',
      value: word.word_breakdown
        ? [
            word.word_breakdown.prefix && { k: 'Prefix', v: word.word_breakdown.prefix },
            word.word_breakdown.root && { k: 'Root', v: word.word_breakdown.root },
            word.word_breakdown.suffix && { k: 'Suffix', v: word.word_breakdown.suffix }
          ].filter(Boolean)
        : '',
      icon: '🧩',
      type: 'chips'
    },
    {
      label: 'Group',
      value: Number.isFinite(word.group_number) ? `Group ${word.group_number}` : '',
      icon: '📚'
    }
  ].filter((it) => (Array.isArray(it.value) ? it.value.length : it.value));

  const categoryBadge =
    word.category ? (
      <span
        className="ur-badge"
        style={{ '--badge-accent': accentColor }}
        title="Part of speech / category"
      >
        {String(word.category).toLowerCase()}
      </span>
    ) : null;

  return (
    <section className="ur-card">
      {/* header row with word + category */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <h3 className="ur-title">
          {word.word}
          {word.pronunciation ? (
            <span className="ur-pron"> /{word.pronunciation}/ </span>
          ) : null}
        </h3>
        {categoryBadge}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {items.map((item, idx) => (
          <div key={idx} className="space-y-2">
            <div className="flex items-center space-x-2">
              <span className="text-base md:text-lg">{item.icon}</span>
              <h4 className="ur-label">{item.label}</h4>
            </div>

            {item.type === 'chips' ? (
              <div className="pl-7 flex flex-wrap gap-2">
                {item.value.map((chip, i) => (
                  <span key={i} className="ur-chip" style={{ '--chip-accent': accentColor }}>
                    <strong className="opacity-80">{chip.k}:</strong>&nbsp;{chip.v}
                  </span>
                ))}
              </div>
            ) : (
              <p className="ur-text pl-7">{item.value}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
