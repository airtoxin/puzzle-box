// Capabilities of these renderers, independent of what a newer server declares.
const renderers = {
  shading: {topology: 'rectangular-cells', maxCells: 100, minSide: 1, required: ['answer'],
    channels: {answer: 'binary-cells', givens: 'cell-givens', 'row-counts': 'row-counts', 'column-counts': 'column-counts', rooms: 'cell-regions', numbers: 'cell-numbers', 'sight-counts': 'cell-sight-counts', 'island-areas': 'cell-island-areas', 'neighbor-counts': 'cell-neighbor-counts', 'component-counts': 'cell-component-counts', 'endpoint-markers': 'cell-endpoint-markers', 'black-runs': 'cell-black-runs', 'component-areas': 'cell-component-areas', 'orthogonal-counts': 'cell-orthogonal-counts'}},
  slitherlink: {topology: 'rectangular-cells', maxCells: 4, minSide: 1, required: ['answer'],
    channels: {answer: 'binary-edges', 'cell-counts': 'cell-edge-counts', 'edge-givens': 'edge-givens'}},
  coupled: {topology: 'rectangular-cell-centers', maxCells: 9, minSide: 2, required: ['answer-cells', 'answer-edges'],
    channels: {'answer-cells': 'binary-cells', 'answer-edges': 'binary-edges', givens: 'cell-givens', 'edge-givens': 'edge-givens'}},
};
export class UnsupportedUiError extends Error {}
function checkedGrid(value, rows, cols, maximum, nullable = false) {
  if (!Array.isArray(value) || value.length !== rows || value.some(row => !Array.isArray(row)
      || row.length !== cols || row.some(n => !(nullable && n === null) && (!Number.isInteger(n) || n < 0 || n > maximum)))) throw new UnsupportedUiError();
  return value;
}
export function canonicalRunClues(value, rows, cols) {
  if (!Array.isArray(value) || value.length !== rows || value.some(row => !Array.isArray(row) || row.length !== cols)) throw new UnsupportedUiError();
  return value.map(row => row.map(clue => {
    if (clue === null) return null;
    if (!Array.isArray(clue) || clue.length < 1 || clue.length > 4
        || clue.some(n => !Number.isInteger(n) || n < 0 || n > 8)
        || clue.includes(0) && !(clue.length === 1 && clue[0] === 0)
        || clue.length > 1 && clue.reduce((a,b) => a+b,0)+clue.length > 8) throw new UnsupportedUiError();
    return [...clue].sort((a,b) => a-b);
  }));
}
function canonicalRooms(value, rows, cols) {
  checkedGrid(value, rows, cols, rows * cols - 1);
  const labels = new Map();
  return value.map(row => row.map(n => {if (!labels.has(n)) labels.set(n, labels.size); return labels.get(n);}));
}
export function assertRenderablePlan(candidate, request) {
  const renderer = Object.hasOwn(renderers, request.family) && renderers[request.family];
  const requirements = candidate?.requirements;
  if (!renderer || candidate?.format !== 'puzzle-box/web-plan-v2' || candidate.family !== request.family
      || candidate.rows !== request.rows || candidate.cols !== request.cols
      || !requirements || requirements.topology !== renderer.topology
      || !Array.isArray(requirements.channels)
      || ![requirements.max_cells, requirements.min_rows, requirements.min_cols].every(n => Number.isInteger(n) && n > 0)
      || ![candidate.rows, candidate.cols].every(n => Number.isInteger(n) && n >= renderer.minSide)
      || candidate.rows < requirements.min_rows || candidate.cols < requirements.min_cols
      || candidate.rows * candidate.cols > Math.min(requirements.max_cells, renderer.maxCells)) throw new UnsupportedUiError();
  const seen = new Set();
  for (const channel of requirements.channels) {
    if (!channel || typeof channel.name !== 'string' || typeof channel.kind !== 'string'
        || !Object.hasOwn(renderer.channels, channel.name) || renderer.channels[channel.name] !== channel.kind
        || seen.has(channel.name)) throw new UnsupportedUiError();
    seen.add(channel.name);
  }
  if (renderer.required.some(name => !seen.has(name))) throw new UnsupportedUiError();
  const requestedRuns = request.rules.filter(r => Object.hasOwn(r.parameters,'run_clues')).map(r => r.parameters.run_clues);
  if (seen.has('black-runs') !== (requestedRuns.length > 0) || !seen.has('black-runs') && candidate.black_run_clues !== undefined) throw new UnsupportedUiError();
  if (seen.has('black-runs')) {
    const shown = JSON.stringify(canonicalRunClues(candidate.black_run_clues,candidate.rows,candidate.cols));
    if (requestedRuns.some(g => JSON.stringify(canonicalRunClues(g,candidate.rows,candidate.cols)) !== shown)) throw new UnsupportedUiError();
  }
  const requestedRooms = request.rules.filter(r => Object.hasOwn(r.parameters, 'rooms')).map(r => r.parameters.rooms);
  if (seen.has('rooms') !== (requestedRooms.length > 0) || !seen.has('rooms') && candidate.rooms !== undefined) throw new UnsupportedUiError();
  if (seen.has('rooms')) {
    const shown = JSON.stringify(canonicalRooms(candidate.rooms, candidate.rows, candidate.cols));
    if (requestedRooms.some(rooms => JSON.stringify(canonicalRooms(rooms, candidate.rows, candidate.cols)) !== shown)) throw new UnsupportedUiError();
  }
  for (const [parameter, channel, payload, maximum = 99, nullable = false] of [['numbers','numbers','numbers'],
    ['orthogonal_counts','orthogonal-counts','orthogonal_counts',4,true], ['component_areas','component-areas','component_areas'], ['counts','sight-counts','sight_counts'], ['areas','island-areas','island_areas'],
    ['neighbor_counts','neighbor-counts','neighbor_counts',8,true], ['component_counts','component-counts','component_counts',99,true], ['markers','endpoint-markers','endpoint_markers',1]]) {
    const requested = request.rules.filter(r => Object.hasOwn(r.parameters, parameter)).map(r => r.parameters[parameter]);
    if (seen.has(channel) !== (requested.length > 0) || !seen.has(channel) && candidate[payload] !== undefined) throw new UnsupportedUiError();
    if (seen.has(channel)) {
      const shown = JSON.stringify(checkedGrid(candidate[payload], candidate.rows, candidate.cols, maximum, nullable));
      if (requested.some(grid => JSON.stringify(checkedGrid(grid, candidate.rows, candidate.cols, maximum, nullable)) !== shown)) throw new UnsupportedUiError();
    }
  }
}
