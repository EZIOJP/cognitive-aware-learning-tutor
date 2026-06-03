import React from 'react';

export default function PillList({ title, items, accentColor = '#4f46e5' }) {
  // Simple but robust handling
  if (!items) return null;
  
  let itemArray = [];
  
  try {
    if (Array.isArray(items)) {
      itemArray = items;
    } else if (typeof items === 'string') {
      itemArray = items.split(',').map(s => s.trim()).filter(s => s);
    } else if (typeof items === 'object' && items !== null) {
      itemArray = Object.values(items).filter(v => v);
    } else {
      itemArray = [String(items)];
    }
  } catch (error) {
    console.error('PillList error:', error);
    return null;
  }
  
  if (itemArray.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 
        className="text-sm font-semibold uppercase tracking-wider"
        style={{ color: accentColor }}
      >
        {title}
      </h3>
      <div className="flex flex-wrap gap-2">
        {itemArray.map((item, idx) => (
          <span
            key={idx}
            className="px-3 py-1 text-sm rounded-full font-medium transition-all duration-200 hover:scale-105 hover:shadow-md"
            style={{
              backgroundColor: `${accentColor}15`,
              color: accentColor,
              border: `1px solid ${accentColor}30`
            }}
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
