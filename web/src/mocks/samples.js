// MOCK: demo tickets for the sidebar queue. Replace with tickets fetched from the helpdesk
// system (or a backend endpoint) when there is a real inbox. Each id must be unique.
export const SAMPLES = [
  {
    id: 'outage',
    label: 'English outage',
    subject: 'Production API down',
    body: 'Since 09:00 UTC our API returns 502 errors for every request. Production is offline and customers cannot check out. We need an update urgently.',
  },
  {
    id: 'billing-de',
    label: 'German billing question',
    subject: 'Doppelte Abbuchung',
    body: 'Hallo, ich wurde diesen Monat doppelt abgebucht. Bitte prüfen Sie meine Rechnung und die Zahlung. Danke!',
  },
  {
    id: 'no-subject',
    label: 'Empty-subject request',
    subject: '',
    body: 'How can I export my account data as CSV? I need it for our quarterly audit.',
  },
  {
    id: 'oos',
    label: 'Out-of-scope request',
    subject: 'Recommendation',
    body: 'Can you recommend a good pizza place in Madrid for our team dinner next week?',
  },
  // The next three describe the same VPN failure, in two languages: run them to raise the outage banner.
  {
    id: 'vpn-1',
    label: 'VPN down (EN)',
    subject: 'VPN not working',
    body: 'Our VPN is not working since this morning. I cannot connect to the office network.',
  },
  {
    id: 'vpn-2',
    label: 'VPN Ausfall (DE)',
    subject: 'VPN Problem',
    body: 'Mein VPN funktioniert seit heute Morgen nicht mehr, ich bekomme keine Verbindung zum Firmennetz.',
  },
  {
    id: 'vpn-3',
    label: 'VPN login failing',
    subject: 'Cannot connect to VPN',
    body: 'The VPN client fails with an authentication error and times out for the whole sales team.',
  },
]
