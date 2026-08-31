/**
 * Phone settings — where the watch sends voice notes.
 */
AppSettingsPage({
  build(props) {
    const storage = props.settingsStorage
    const get = (k, d) => {
      const v = storage.getItem(k)
      return v !== undefined && v !== null && v !== '' ? v : d
    }

    return View(
      {
        style: {
          padding: '12px 16px',
          fontFamily: 'system-ui, sans-serif',
          paddingBottom: '48px',
        },
      },
      [
        Text(
          { style: { fontSize: '18px', fontWeight: '600', marginBottom: '4px' } },
          ['CALT Voice'],
        ),
        Text(
          {
            style: {
              fontSize: '13px',
              color: '#b45309',
              background: '#fff7ed',
              padding: '10px',
              borderRadius: '8px',
              marginBottom: '14px',
              lineHeight: '1.45',
            },
          },
          [
            'Same hub as CALT Sync. Base URL = desktop tracker hub http://<PC-LAN-IP>:8765. ' +
              'Record on the watch, swipe left for Files, then tap a clip to send. ' +
              'Transfers run over Bluetooth and are slow — a long clip can take several minutes. ' +
              'A clip is deleted from the watch only after a receiver re-hashes it and confirms.',
          ],
        ),

        TextInput({
          label: 'Base URL (tracker hub)',
          value: get('base_url', 'http://192.168.0.110:8765'),
          onChange: (val) => storage.setItem('base_url', String(val || '').trim()),
        }),
        Text(
          {
            style: {
              fontSize: '12px',
              color: '#7f1d1d',
              background: '#fef2f2',
              padding: '10px',
              borderRadius: '8px',
              marginTop: '8px',
              lineHeight: '1.45',
            },
          },
          [
            'Use your PC LAN IP — localhost / 127.0.0.1 will NOT work from the phone. ' +
              'Verify: open http://<IP>:8765/health in the phone browser.',
          ],
        ),
        TextInput({
          label: 'Fallback URL (optional, used when the PC is off)',
          value: get('fallback_url', ''),
          onChange: (val) => storage.setItem('fallback_url', String(val || '').trim()),
        }),
        TextInput({
          label: 'Ingest token',
          value: get('ingest_token', 'calt-local-wearables'),
          onChange: (val) => storage.setItem('ingest_token', val),
        }),

        Text(
          {
            style: {
              fontSize: '12px',
              color: '#7f1d1d',
              background: '#fef2f2',
              padding: '10px',
              borderRadius: '8px',
              marginTop: '14px',
              lineHeight: '1.45',
            },
          },
          [
            'The phone itself cannot store clips. Zepp OS gives a side service only ' +
              'Messaging, Fetch and Settings — no filesystem read API — so it can relay ' +
              'bytes but never hold or hand them to you. If the PC is often off, run the ' +
              'same voice-note endpoints somewhere always-on and put that address in ' +
              'Fallback URL. Otherwise clips stay on the watch until the PC is back.',
          ],
        ),

        Text(
          {
            style: {
              fontSize: '12px',
              color: '#666',
              marginTop: '16px',
              lineHeight: '1.45',
              padding: '10px',
              background: '#f5f5f5',
              borderRadius: '8px',
              whiteSpace: 'pre-wrap',
            },
          },
          [`Last hub host: ${get('last_note_host', '—')}\nNotes land in data/voice_notes/ on the PC.`],
        ),
      ],
    )
  },
})
