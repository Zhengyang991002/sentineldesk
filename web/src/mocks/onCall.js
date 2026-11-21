import manager1 from '../../assets/manager_1.jpg'
import manager2 from '../../assets/manager_2.jpg'

// MOCK: avatars shown when a ticket is escalated. Replace with the engineers that are
// actually on call (from PagerDuty, Opsgenie, or a backend endpoint).
// `position` and `origin` frame the face inside the round avatar.
export const ON_CALL = [
  { id: 'manager-1', name: 'On-call manager', photo: manager1, position: '46% 30%', origin: '46% 35%' },
  { id: 'manager-2', name: 'On-call manager', photo: manager2, position: '45% 45%', origin: '45% 48%' },
]
