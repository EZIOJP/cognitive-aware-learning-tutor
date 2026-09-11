#pragma once

#include <string>

/** Journal + Bible day SoT in vocab_app.db (Focus / enforcer owned). */
void LifeEnsureTables();

// --- Journal (user_id default 1) ---
std::string LifeJournalSummaryJson(const std::string& dayYmd, int userId = 1);
std::string LifeJournalLogJson(int limit, int userId = 1);
bool LifeJournalUpsert(const std::string& payloadJson, int userId, std::string* outEntryJson);

// --- Bible progress ---
/** Ensure today's row; import legacy day_*.json once if SQLite empty. */
void LifeBibleEnsureToday(int userId, const std::wstring& bibleDataDir);

std::string LifeBibleTodayJson(int userId, const std::wstring& bibleDataDir);
std::string LifeBibleStateJson(int userId, const std::wstring& bibleDataDir);

/** Mark assigned chapter done/undone; updates SoftLand goals.bible_done + publishes. */
bool LifeBibleTick(int userId, const std::string& book, int chapter, bool done,
                   const std::wstring& bibleDataDir, const std::wstring& behaviorDir,
                   std::string* outStateJson);

bool LifeBibleHeartbeat(int userId, const std::string& book, int chapter, bool focused,
                        const std::wstring& bibleDataDir, std::string* outStateJson);

bool LifeBibleDevotionDone(int userId, const std::string& slot, bool done,
                           const std::wstring& bibleDataDir, const std::wstring& behaviorDir,
                           std::string* outJson);

bool LifeBibleDevotionNotes(int userId, const std::string& slot, const std::string& notes,
                            const std::wstring& bibleDataDir, std::string* outJson);

std::string LifeBibleDevotionTodayJson(int userId, const std::wstring& bibleDataDir);
