/**
 * Phone Settings App — durations & classic lock.
 */
AppSettingsPage({
  build(props) {
    const { settingsStorage } = props
    let focusMin = Number(settingsStorage.getItem('focusMin') || 25)
    let shortBreakMin = Number(settingsStorage.getItem('shortBreakMin') || 5)
    let longBreakMin = Number(settingsStorage.getItem('longBreakMin') || 15)
    let lockClassic = settingsStorage.getItem('lockClassic') === '1'
    let sensitivity = settingsStorage.getItem('sensitivity') || 'normal'

    return View(
      { style: { padding: 16 } },
      [
        Text({ style: { fontSize: 20, fontWeight: 'bold' } }, 'Adaptive Focus'),
        Text({ style: { marginTop: 8, color: '#888' } }, 'Watch syncs these when you open Settings.'),
        Text({ style: { marginTop: 16 } }, `Focus minutes: ${focusMin}`),
        Button({
          label: '−5',
          style: { margin: 4 },
          onClick: () => {
            focusMin = Math.max(15, focusMin - 5)
            settingsStorage.setItem('focusMin', String(focusMin))
          },
        }),
        Button({
          label: '+5',
          style: { margin: 4 },
          onClick: () => {
            focusMin = Math.min(50, focusMin + 5)
            settingsStorage.setItem('focusMin', String(focusMin))
          },
        }),
        Text({ style: { marginTop: 12 } }, `Short break: ${shortBreakMin}m · Long: ${longBreakMin}m`),
        Button({
          label: lockClassic ? 'Classic 25/5: ON' : 'Classic 25/5: OFF',
          style: { marginTop: 12 },
          onClick: () => {
            lockClassic = !lockClassic
            settingsStorage.setItem('lockClassic', lockClassic ? '1' : '0')
          },
        }),
        Text({ style: { marginTop: 12 } }, `Sensitivity: ${sensitivity}`),
        Button({
          label: 'Cycle sensitivity',
          onClick: () => {
            sensitivity =
              sensitivity === 'normal' ? 'sensitive' : sensitivity === 'sensitive' ? 'calm' : 'normal'
            settingsStorage.setItem('sensitivity', sensitivity)
          },
        }),
        Text(
          { style: { marginTop: 20, fontSize: 12, color: '#666' } },
          'Device App also stores af_settings_v1 on-watch. Re-open the watch app after changing.',
        ),
      ],
    )
  },
})
