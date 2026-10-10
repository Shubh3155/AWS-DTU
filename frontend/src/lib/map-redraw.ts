// A GeoJSON update can briefly mark a loaded style as not fully loaded.
// Existing sources can still be updated; a first draw waits for readiness.
type MapReadiness = {
  isStyleLoaded: () => boolean | undefined;
  getSource: (id: string) => unknown;
  once: (event: "idle", callback: () => void) => unknown;
  off: (event: "idle", callback: () => void) => unknown;
};

export function scheduleRouteDraw(map: MapReadiness, draw: () => void) {
  if (map.getSource("walking-routes") || map.isStyleLoaded()) draw();
  else map.once("idle", draw);
  return () => { map.off("idle", draw); };
}
