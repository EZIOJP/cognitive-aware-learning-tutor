// ============================================================
// SelfTracker — content.js  v2.0
// Deep behavioral spy: generic tracking + Scalar & YouTube
// deep-dive scrapers for course/video progress
// ============================================================

(function () {
  if (window.__selfTrackerLoaded) return;
  window.__selfTrackerLoaded = true;

  const HOST = location.hostname;
  const IS_YOUTUBE = HOST.includes('youtube.com');
  const IS_SCALAR  = HOST.includes('scalar.com') || HOST.includes('scalar.dev');

  // ──────────────────────────────────────────────────────────
  // Generic behavioral state
  // ──────────────────────────────────────────────────────────
  const state = {
    scrollDepthMax: 0,
    scrollEvents: [],
    mouseClicks: 0,
    keystrokes: 0,
    mouseMovements: 0,
    lastMouseTime: 0,
    lastScrollY: window.scrollY,
    lastScrollTime: Date.now(),
    idleStart: Date.now(),
    isIdle: false,
    pageLoadTime: Date.now(),
    textLength: 0,
    wordCount: 0
  };

  // ── Generic text scrape ───────────────────────────────────
  function scrapeContext() {
    const article = document.querySelector('article, main, [role="main"], .content, #content, .post-body');
    const text = article
      ? article.innerText.slice(0, 600)
      : document.body.innerText.slice(0, 600);
    const words = text.trim().split(/\s+/).filter(Boolean);
    state.wordCount = words.length;
    state.textLength = text.length;
    return text.trim().replace(/\n+/g, ' ').slice(0, 300);
  }

  // ──────────────────────────────────────────────────────────
  // SCALAR deep scraper
  // Extracts: current chapter, total chapters, sidebar items,
  // completed items (marked with ✓ or .is-complete etc.)
  // ──────────────────────────────────────────────────────────
  function scrapeScalar() {
    const data = { site: 'scalar' };

    // Page title / current section
    data.page_title = document.title;

    // Current section heading
    const heading = document.querySelector('h1, h2, .section-title, [data-title]');
    data.current_section = heading ? heading.innerText.trim().slice(0, 120) : '';

    // Try to find the sidebar navigation for progress
    const navLinks = Array.from(document.querySelectorAll(
      'nav a, aside a, [class*="sidebar"] a, [class*="menu"] a, [class*="nav"] a, [class*="toc"] a'
    ));

    if (navLinks.length > 0) {
      const allItems = navLinks.map(a => ({
        title: a.innerText.trim().slice(0, 80),
        href: a.getAttribute('href') || '',
        // detect completion via classes or aria
        completed: (
          a.classList.contains('is-complete') ||
          a.classList.contains('completed') ||
          a.classList.contains('done') ||
          a.getAttribute('aria-current') === 'page' ||
          a.querySelector('[class*="check"], [class*="done"], svg') !== null ||
          a.innerText.includes('✓') || a.innerText.includes('✔')
        ),
        active: (
          a.getAttribute('aria-current') === 'page' ||
          a.classList.contains('active') ||
          a.classList.contains('current') ||
          window.location.pathname === a.getAttribute('href')
        ),
      })).filter(item => item.title.length > 1);

      data.total_nav_items = allItems.length;
      data.completed_items = allItems.filter(i => i.completed).length;
      data.active_item = allItems.find(i => i.active)?.title || data.current_section;
      data.completion_percent = allItems.length > 0
        ? Math.round((data.completed_items / allItems.length) * 100)
        : 0;
      data.remaining_items = allItems.length - data.completed_items;
      data.nav_items_preview = allItems.slice(0, 10);
    }

    // Reading progress on current page
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    data.page_scroll_percent = docHeight > 0 ? Math.round((scrollTop / docHeight) * 100) : 0;

    // Visible code blocks count (indicates technical depth)
    data.code_blocks_visible = document.querySelectorAll('pre code, .code-block, [class*="codeBlock"]').length;

    // Estimate reading time left on this page
    const articleText = document.querySelector('article, main, .content');
    if (articleText) {
      const wordCount = articleText.innerText.split(/\s+/).length;
      const readSoFar = Math.round((data.page_scroll_percent / 100) * wordCount);
      data.words_remaining_on_page = Math.max(0, wordCount - readSoFar);
      data.est_mins_remaining_on_page = Math.round(data.words_remaining_on_page / 200);
    }

    return data;
  }

  // ──────────────────────────────────────────────────────────
  // YOUTUBE deep scraper
  // Extracts: video title, channel, duration, watched %,
  // playlist info, chapters, watch state
  // ──────────────────────────────────────────────────────────
  function scrapeYouTube() {
    const data = { site: 'youtube' };

    const video = document.querySelector('video');

    if (video) {
      const duration = video.duration || 0;
      const currentTime = video.currentTime || 0;
      data.video_duration_seconds = Math.round(duration);
      data.video_current_seconds = Math.round(currentTime);
      data.video_watched_percent = duration > 0 ? Math.round((currentTime / duration) * 100) : 0;
      data.video_completed = data.video_watched_percent >= 90;
      data.video_paused = video.paused;
      data.video_muted = video.muted;
    }

    // Title
    const titleEl = document.querySelector('h1.ytd-video-primary-info-renderer, .ytd-watch-metadata h1, h1.style-scope');
    data.video_title = titleEl ? titleEl.innerText.trim().slice(0, 200) : document.title;

    // Channel
    const channelEl = document.querySelector('#channel-name a, .ytd-channel-name a, #owner a');
    data.channel_name = channelEl ? channelEl.innerText.trim() : '';

    // Playlist / series info
    const playlistPanel = document.querySelector('#playlist, ytd-playlist-panel-renderer');
    if (playlistPanel) {
      const playlistTitle = playlistPanel.querySelector('#playlist-title, h3, .title');
      data.playlist_title = playlistTitle ? playlistTitle.innerText.trim().slice(0, 100) : '';

      // Count items in playlist
      const playlistItems = playlistPanel.querySelectorAll('ytd-playlist-panel-video-renderer');
      data.playlist_total = playlistItems.length;

      // Find current video position in playlist
      const currentItem = playlistPanel.querySelector('.selected, [aria-selected="true"], .ytd-playlist-panel-video-renderer[selected]');
      const currentIdx = currentItem
        ? Array.from(playlistItems).indexOf(currentItem)
        : -1;
      data.playlist_current_index = currentIdx >= 0 ? currentIdx + 1 : null;
      data.playlist_videos_remaining = currentIdx >= 0 ? data.playlist_total - currentIdx - 1 : null;
      data.playlist_completion_percent = (currentIdx >= 0 && data.playlist_total > 0)
        ? Math.round(((currentIdx + 1) / data.playlist_total) * 100)
        : 0;
    }

    // Video chapters (if present)
    const chapterEls = document.querySelectorAll('.ytp-chapter-title-content, [class*="chapter"]');
    if (chapterEls.length > 0) {
      data.chapters = Array.from(chapterEls)
        .map(el => el.innerText.trim())
        .filter(t => t.length > 0)
        .slice(0, 10);
      data.chapters_count = data.chapters.length;
    }

    // Currently active chapter
    const activeChapter = document.querySelector('.ytp-chapter-title-content');
    data.current_chapter = activeChapter ? activeChapter.innerText.trim() : '';

    // View count (indicates content relevance/quality signal)
    const viewsEl = document.querySelector('.view-count, .ytd-video-view-count-renderer');
    data.view_count_text = viewsEl ? viewsEl.innerText.trim() : '';

    // Is this a shorts/regular video
    data.is_shorts = location.pathname.startsWith('/shorts');
    data.is_live = !!document.querySelector('.ytp-live-badge, .ytp-live');

    // Classify learning vs leisure by title/channel heuristics
    const titleLower = (data.video_title || '').toLowerCase();
    data.content_type = 
      titleLower.match(/tutorial|course|learn|lecture|how to|guide|explained|introduction|bootcamp|crash course|full stack|javascript|python|react|ml|ai|math/)
        ? 'Educational'
        : titleLower.match(/vlog|daily|day in|prank|reaction|funny|meme|gaming|gameplay/)
          ? 'Leisure'
          : 'Unclassified';

    return data;
  }

  // ── Scroll tracking ──────────────────────────────────────
  function getScrollDepthPercent() {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    return docHeight > 0 ? Math.round((scrollTop / docHeight) * 100) : 0;
  }

  window.addEventListener('scroll', () => {
    const now = Date.now();
    const currentY = window.scrollY;
    const dt = (now - state.lastScrollTime) || 1;
    const velocity = Math.abs(currentY - state.lastScrollY) / dt;

    state.scrollEvents.push(velocity);
    if (state.scrollEvents.length > 50) state.scrollEvents.shift();

    const depth = getScrollDepthPercent();
    if (depth > state.scrollDepthMax) state.scrollDepthMax = depth;

    state.lastScrollY = currentY;
    state.lastScrollTime = now;
    resetIdle();
  }, { passive: true });

  document.addEventListener('click', () => { state.mouseClicks++; resetIdle(); });
  document.addEventListener('mousemove', () => {
    const now = Date.now();
    if (now - state.lastMouseTime > 500) { state.mouseMovements++; state.lastMouseTime = now; }
    resetIdle();
  }, { passive: true });
  document.addEventListener('keydown', () => { state.keystrokes++; resetIdle(); });

  // ── Idle detection ────────────────────────────────────────
  const IDLE_THRESHOLD = 30000;
  let idleTimer = null;

  function resetIdle() {
    state.isIdle = false;
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      state.isIdle = true;
      state.idleStart = Date.now();
    }, IDLE_THRESHOLD);
  }
  resetIdle();

  // ── Interaction mode ─────────────────────────────────────
  function getInteractionMode() {
    const avgVel = state.scrollEvents.length
      ? state.scrollEvents.reduce((a, b) => a + b, 0) / state.scrollEvents.length
      : 0;
    if (IS_YOUTUBE) {
      const video = document.querySelector('video');
      if (video && !video.paused) return 'watching_video';
    }
    if (state.isIdle) return 'idle';
    if (state.keystrokes > 20) return 'writing';
    if (state.mouseClicks > 10) return 'active_clicking';
    if (avgVel > 3) return 'skimming';
    if (avgVel > 0.3) return 'reading';
    if (state.mouseMovements < 3 && !state.isIdle) return 'passive_watching';
    return 'browsing';
  }

  // ── Build and send snapshot ──────────────────────────────
  function sendSnapshot() {
    const basePayload = {
      interaction_mode: getInteractionMode(),
      scroll_depth_percent: state.scrollDepthMax,
      scroll_velocity_avg: state.scrollEvents.length
        ? parseFloat((state.scrollEvents.reduce((a, b) => a + b, 0) / state.scrollEvents.length).toFixed(3))
        : 0,
      mouse_clicks: state.mouseClicks,
      keystrokes: state.keystrokes,
      mouse_movements: state.mouseMovements,
      is_idle: state.isIdle,
      time_on_page_seconds: Math.round((Date.now() - state.pageLoadTime) / 1000),
      page_title: document.title,
      scraped_text_preview: scrapeContext(),
      word_count_visible: state.wordCount,
    };

    // Merge deep-scrape data for special sites
    let deepData = {};
    if (IS_SCALAR)  deepData = scrapeScalar();
    if (IS_YOUTUBE) deepData = scrapeYouTube();

    chrome.runtime.sendMessage({
      type: 'BEHAVIORAL_UPDATE',
      data: { ...basePayload, ...deepData }
    });

    // Reset per-interval counters
    state.mouseClicks = 0;
    state.keystrokes = 0;
    state.mouseMovements = 0;
    state.scrollDepthMax = getScrollDepthPercent();
  }

  // For YouTube, also listen to video time updates to catch completions
  if (IS_YOUTUBE) {
    const attachVideoListener = () => {
      const video = document.querySelector('video');
      if (video && !video.__selfTrackerBound) {
        video.__selfTrackerBound = true;
        video.addEventListener('ended', () => {
          chrome.runtime.sendMessage({
            type: 'BEHAVIORAL_UPDATE',
            data: { ...scrapeYouTube(), event: 'VIDEO_COMPLETED', page_title: document.title }
          });
        });
        // Also send at 25%, 50%, 75% milestones
        let milestonesSent = new Set();
        video.addEventListener('timeupdate', () => {
          const pct = video.duration > 0 ? Math.round((video.currentTime / video.duration) * 100) : 0;
          [25, 50, 75].forEach(milestone => {
            if (pct >= milestone && !milestonesSent.has(milestone)) {
              milestonesSent.add(milestone);
              chrome.runtime.sendMessage({
                type: 'BEHAVIORAL_UPDATE',
                data: { ...scrapeYouTube(), event: `VIDEO_${milestone}PCT`, page_title: document.title }
              });
            }
          });
        });
      }
    };
    // YT is a SPA — retry attaching on DOM changes
    setInterval(attachVideoListener, 2000);
  }

  setInterval(sendSnapshot, 30000);
  setTimeout(sendSnapshot, 5000);
})();
