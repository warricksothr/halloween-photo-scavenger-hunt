// "N min ago" for queue rows, history and rosters.
export function ago(createdAt) {
  const mins = Math.max(0, Math.round((Date.now() / 1000 - createdAt) / 60));
  return mins < 1 ? 'just now' : `${mins} min ago`;
}
