import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useTheme } from '../../../context/ThemeContext';
import { ThemeToggle } from '../../../components/theme/ThemeToggle';
import InfoGrid from './InfoGrid';
import Examples from './Examples';
import PillList from './PillList';
import Links from './Links';
import './UniversalReadMode.css';

// Simple page animation (no complex 3D stuff)
const pageVariants = {
  enter: (direction) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction) => ({
    x: direction < 0 ? 300 : -300,
    opacity: 0,
  })
};

const pageTransition = {
  type: "spring",
  stiffness: 280,
  damping: 30
};

export default function UniversalReadMode({ 
  fetchWords, 
  title = "Read Mode",
  allowFiltering = true,
  markAsRead = true,
  className = "",
  onWordChange = null,
  customFilters = [],
  showStats = true
}) {
  // Simple state - no complex pagination/preloading
  const [allWords, setAllWords] = useState([]);
  const [index, setIndex] = useState(0);
  const [showUI, setShowUI] = useState(true);
  const [wordFilter, setWordFilter] = useState('all');
  const [direction, setDirection] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Refs
  const containerRef = useRef(null);
  const hideUITimeout = useRef(null);
  const { isDarkMode } = useTheme();

  // Simple UI timer
  const resetHideTimer = useCallback(() => {
    setShowUI(true);
    clearTimeout(hideUITimeout.current);
    hideUITimeout.current = setTimeout(() => setShowUI(false), 4000);
  }, []);

  // Simple filtering (no complex mastery logic)
  const filteredWords = useMemo(() => {
    if (!allowFiltering || wordFilter === 'all') return allWords;

    switch (wordFilter) {
      case 'unlearned':
        return allWords.filter(w => (w.mastery || 0) === 0);
      case 'low-mastery':
        return allWords.filter(w => (w.mastery || 0) <= 2);
      case 'struggling':
        return allWords.filter(w => (w.mastery || 0) < 0);
      case 'practicing':
        return allWords.filter(w => {
          const mastery = w.mastery || 0;
          return mastery >= 3 && mastery <= 5;
        });
      case 'mastered':
        return allWords.filter(w => (w.mastery || 0) >= 6);
      case 'due-review':
        return allWords.filter(w => w.is_due);
      default:
        const customFilter = customFilters.find(f => f.key === wordFilter);
        return customFilter?.filter ? allWords.filter(customFilter.filter) : allWords;
    }
  }, [allWords, wordFilter, allowFiltering, customFilters]);

  // Simple navigation - no preloading complexity
  const handleSwipe = useCallback((swipeDirection) => {
    if (!filteredWords.length) return;
    
    const currentWord = filteredWords[index];
    
    // Simple marking as read (deferred to avoid blocking)
    if (swipeDirection === 1 && currentWord && markAsRead) {
      setTimeout(() => {
        import('../api/readModeAPI').then(({ markSwipeRead }) => {
          markSwipeRead(currentWord.id).catch(console.warn);
        });
      }, 100);
    }
    
    setDirection(swipeDirection);
    const newIndex = (index + swipeDirection + filteredWords.length) % filteredWords.length;
    setIndex(newIndex);
    
    if (onWordChange && filteredWords[newIndex]) {
      onWordChange(filteredWords[newIndex], newIndex);
    }
    
    resetHideTimer();
  }, [index, filteredWords, markAsRead, onWordChange, resetHideTimer]);

  // Simple keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      resetHideTimer();
      switch (e.key.toLowerCase()) {
        case 'arrowleft':
        case 'h':
        case 'a':
          e.preventDefault();
          handleSwipe(-1);
          break;
        case 'arrowright':
        case ' ':
        case 'l':
        case 'd':
          e.preventDefault();
          handleSwipe(1);
          break;
        case 'escape':
        case 'u':
          e.preventDefault();
          setShowUI(prev => !prev);
          break;
        case 'r':
          e.preventDefault();
          if (filteredWords.length > 1) {
            const randomIndex = Math.floor(Math.random() * filteredWords.length);
            setDirection(randomIndex > index ? 1 : -1);
            setIndex(randomIndex);
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSwipe, resetHideTimer, filteredWords, index]);

  // Simple touch/mouse handlers
  useEffect(() => {
    const handleMouseMove = () => resetHideTimer();
    const handleClick = (e) => {
      if (!containerRef.current) return;
      
      const rect = containerRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      
      // Ignore clicks on UI elements
      if (e.target.closest('.read-mode-header') || e.target.closest('.read-mode-navigation')) {
        return;
      }

      const thirdWidth = rect.width / 3;
      if (clickX < thirdWidth) {
        handleSwipe(-1);
      } else if (clickX > thirdWidth * 2) {
        handleSwipe(1);
      } else {
        setShowUI(prev => !prev);
      }
    };

    // Touch gestures
    let touchStartX = 0;
    const handleTouchStart = (e) => {
      touchStartX = e.touches[0].clientX;
      resetHideTimer();
    };

    const handleTouchEnd = (e) => {
      if (!touchStartX) return;
      
      const touchEndX = e.changedTouches[0].clientX;
      const diffX = touchStartX - touchEndX;
      const minSwipeDistance = 50;

      if (Math.abs(diffX) > minSwipeDistance) {
        if (diffX > 0) {
          handleSwipe(1); // Swipe left -> next
        } else {
          handleSwipe(-1); // Swipe right -> previous
        }
      }
      touchStartX = 0;
    };

    window.addEventListener('mousemove', handleMouseMove);
    const currentContainer = containerRef.current;
    currentContainer?.addEventListener('click', handleClick);
    currentContainer?.addEventListener('touchstart', handleTouchStart);
    currentContainer?.addEventListener('touchend', handleTouchEnd);

    resetHideTimer();

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (currentContainer) {
        currentContainer.removeEventListener('click', handleClick);
        currentContainer.removeEventListener('touchstart', handleTouchStart);
        currentContainer.removeEventListener('touchend', handleTouchEnd);
      }
      clearTimeout(hideUITimeout.current);
    };
  }, [handleSwipe, resetHideTimer]);

  // Simple loading - just fetch once
  useEffect(() => {
    let cancelled = false;
    
    const loadWords = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const response = await fetchWords();
        if (cancelled) return;
        
        // Handle both paginated and legacy responses
        const words = response.words || response;
        
        const processedWords = words.map(word => ({
          ...word,
          mastery: word.mastery || 0,
          times_asked: word.times_asked || 0,
          times_correct: word.times_correct || 0,
          accuracy_rate: word.accuracy_rate || 0,
          is_due: word.is_due || false
        }));
        
        setAllWords(processedWords);
        setIsLoading(false);
        
      } catch (e) {
        if (!cancelled) {
          console.error('Error fetching words:', e);
          setError(e.message || 'Failed to load words. Please try again.');
          setIsLoading(false);
        }
      }
    };

    loadWords();
    
    return () => {
      cancelled = true;
    };
  }, [fetchWords]);

  // Reset index when filtering
  useEffect(() => {
    setIndex(0);
  }, [filteredWords]);

  // Loading state
  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-gray-900 flex items-center justify-center">
        <div className="text-center text-white">
          <motion.div
            animate={{ 
              rotate: 360,
              scale: [1, 1.1, 1]
            }}
            transition={{ 
              rotate: { duration: 2, repeat: Infinity, ease: "linear" },
              scale: { duration: 1, repeat: Infinity, ease: "easeInOut" }
            }}
            className="text-6xl mb-4"
          >
            ðŸ“š
          </motion.div>
          <h2 className="text-2xl font-bold">Loading {title}...</h2>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="fixed inset-0 bg-gray-900 flex items-center justify-center">
        <div className="text-center text-white">
          <div className="text-6xl mb-4">âš ï¸</div>
          <h2 className="text-2xl font-bold mb-4">Oops! Something went wrong</h2>
          <p className="mb-6">{error}</p>
          <motion.button 
            onClick={() => window.location.reload()}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold"
          >
            Try Again
          </motion.button>
        </div>
      </div>
    );
  }

  // Empty state
  if (!filteredWords.length) {
    return (
      <div className="fixed inset-0 bg-gray-900 flex items-center justify-center">
        <div className="text-center text-white">
          <div className="text-6xl mb-4">ðŸ“–</div>
          <h2 className="text-2xl font-bold mb-4">No words found</h2>
          <p className="mb-6">Try adjusting your filters or check back later.</p>
          {allowFiltering && wordFilter !== 'all' && (
            <motion.button 
              onClick={() => setWordFilter('all')}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold"
            >
              Show All Words
            </motion.button>
          )}
        </div>
      </div>
    );
  }

  const currentWord = filteredWords[index];
  const progress = ((index + 1) / filteredWords.length) * 100;

  // Get available filters
  const filterOptions = [
    { key: 'all', label: `All Words (${allWords.length})`, count: allWords.length }
  ];

  if (allowFiltering) {
    filterOptions.push(
      { 
        key: 'unlearned', 
        label: 'Unlearned', 
        count: allWords.filter(w => (w.mastery || 0) === 0).length 
      },
      { 
        key: 'low-mastery', 
        label: 'Low Mastery', 
        count: allWords.filter(w => (w.mastery || 0) <= 2).length 
      },
      { 
        key: 'struggling', 
        label: 'Struggling', 
        count: allWords.filter(w => (w.mastery || 0) < 0).length 
      },
      { 
        key: 'practicing', 
        label: 'Practicing', 
        count: allWords.filter(w => {
          const mastery = w.mastery || 0;
          return mastery >= 3 && mastery <= 5;
        }).length 
      },
      { 
        key: 'mastered', 
        label: 'Mastered', 
        count: allWords.filter(w => (w.mastery || 0) >= 6).length 
      }
    );

    if (allWords.some(w => w.is_due)) {
      filterOptions.push({
        key: 'due-review',
        label: 'Due Review',
        count: allWords.filter(w => w.is_due).length
      });
    }

    // Add custom filters
    customFilters.forEach(filter => {
      filterOptions.push({
        key: filter.key,
        label: filter.label,
        count: allWords.filter(filter.filter).length
      });
    });
  }

  return (
    <div 
      ref={containerRef}
      className={`fixed inset-0 bg-gray-900 z-50 overflow-hidden ${className}`}
    >
      {/* Header - Your Old Style */}
      <AnimatePresence>
        {showUI && (
          <motion.div
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -50 }}
            transition={{ duration: 0.4 }}
            className="absolute top-0 left-0 right-0 z-10 bg-gradient-to-b from-black/60 to-transparent p-4"
          >
            <div className="flex items-center justify-between text-white">
              <div className="flex items-center space-x-4">
                {allowFiltering && (
                  <select
                    value={wordFilter}
                    onChange={(e) => setWordFilter(e.target.value)}
                    className="bg-white/20 text-white border-none rounded-lg px-4 py-2 focus:outline-none focus:bg-white/30"
                  >
                    {filterOptions.map(option => (
                      <option key={option.key} value={option.key} className="text-black">
                        {option.label} ({option.count})
                      </option>
                    ))}
                  </select>
                )}
                <ThemeToggle />
              </div>
              
              <div className="flex items-center space-x-6">
                <span className="text-lg font-medium">
                  {index + 1} / {filteredWords.length}
                </span>
                <div className="w-40 bg-white/30 rounded-full h-3">
                  <motion.div 
                    className="bg-white rounded-full h-3 transition-all duration-500"
                    animate={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content - Your Old Card Design */}
      <div className="h-full flex items-center justify-center p-6 pt-10">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={currentWord.id}
            custom={direction}
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={pageTransition}
            className="w-full max-w-5xl mx-auto max-h-full overflow-auto no-scrollbar"
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.28}
            onDragEnd={(_, info) => {
              resetHideTimer();
              if (info.offset.x < -120) handleSwipe(1);     // swipe left â†’ next
              else if (info.offset.x > 120) handleSwipe(-1); // swipe right â†’ prev
            }}
          >
            {/* Your Original Beautiful Card Design */}
            <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-2xl overflow-hidden">
              {/* Header - Your Original Style */}
              <header className="px-8 py-8 bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-800 dark:via-gray-700 dark:to-gray-600 border-b border-gray-100 dark:border-gray-700">
                <div className="flex flex-wrap items-center justify-between gap-6">
                  <h1 className="text-3xl md:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">
                    {currentWord.word}
                  </h1>
                  <div className="flex items-center gap-6">
                    {currentWord.pronunciation && (
                      <span className="text-2xl md:text-3xl italic text-gray-600 dark:text-gray-300 select-all">
                        /{currentWord.pronunciation}/
                      </span>
                    )}
                    {showStats && (
                      <div className="flex items-center gap-2 bg-white/50 dark:bg-gray-700/50 rounded-full px-4 py-2">
                        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                          Mastery:
                        </span>
                        <span className={`text-lg font-bold px-3 py-1 rounded-full ${
                          (currentWord.mastery || 0) < 0 ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                          (currentWord.mastery || 0) <= 2 ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                          (currentWord.mastery || 0) <= 5 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                          'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        }`}>
                          {currentWord.mastery || 0}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </header>

              {/* Content - Your Original Layout */}
              <main className="p-8 space-y-8">
                <InfoGrid word={currentWord} />
                <Examples word={currentWord} />
                
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                  <PillList title="Synonyms" items={currentWord.synonyms} />
                  <PillList title="Antonyms" items={currentWord.antonyms} />
                  <PillList title="Groups" items={currentWord.word_grouping || []} />
                  <PillList title="Tags" items={currentWord.tags} />
                </div>
                
                <Links word={currentWord} />
              </main>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation Hints */}
      <AnimatePresence>
        {showUI && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            transition={{ duration: 0.4 }}
            className="absolute bottom-0 left-0 right-0 z-10 bg-gradient-to-t from-black/60 to-transparent p-4"
          >
            <div className="flex items-center justify-between text-white text-sm">
              <div className="flex flex-col items-start">
                <span className="font-medium">â† Previous</span>
                <small className="text-white/80">â† or H</small>
              </div>
              
              <div className="flex flex-col items-center">
                <span className="font-medium">Controls</span>
                <small className="text-white/80">Space: next â€¢ ESC: toggle â€¢ R: random</small>
              </div>
              
              <div className="flex flex-col items-end">
                <span className="font-medium">Next â†’</span>
                <small className="text-white/80">â†’ or L</small>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}