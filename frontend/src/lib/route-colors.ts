// The API returns at most three candidates. Share their colours across map and cards.
const ROUTE_COLORS = ["#0072b2", "#8b3fb0", "#d55e00"] as const;

export function routeColor(index: number): string {
  return ROUTE_COLORS[index % ROUTE_COLORS.length];
}
