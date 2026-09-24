// "N min ago" / "N h ago" / "N d ago" for queue rows, history and rosters.
// Minutes alone read badly once a party runs long ("745 min ago").
export function ago(createdAt, now = Date.now() / 1000) {
  const mins = Math.max(0, Math.round((now - createdAt) / 60));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.floor(hours / 24)} d ago`;
}
