/**
 * Foreground/background verse toast. Keep this free of @zos/app-service
 * so the App Service can import it without a cycle.
 */
import * as notificationMgr from '@zos/notification'
import { log as Logger } from '@zos/utils'

const logger = Logger.getLogger('calt-bible-notify')

export function sendVerseNotification(verse, vibrate) {
  if (!verse) return false
  try {
    notificationMgr.notify({
      title: String(verse.ref || 'CALT Bible').slice(0, 48),
      content: String(verse.text || '').slice(0, 120),
      actions: [
        {
          text: 'Read',
          file: 'page/index',
        },
      ],
      vibrate: vibrate == null ? 6 : vibrate,
    })
    return true
  } catch (e) {
    logger.log(`notify ${e}`)
    return false
  }
}
