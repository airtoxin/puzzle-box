"""Exhaustively diagnose small recipes using built-in shading rules."""

import argparse
from collections.abc import Iterable
from itertools import combinations, product, groupby
import json
from pathlib import Path
import platform
from typing import Any

import ortools

from puzzle import Cell
from puzzle_defs import (BlackCount, ColumnCountClue, ConnectedWhite, NonTouchingBlack,
                         NoWhite2x2, RowCountClue, ShadingPuzzle, ShadingRecipe,
                         BalancedLines, BlackDominoes, ConnectedBlack, DistinctLines,
                         NoBlack2x2, NoThreeConsecutive)
from puzzle_defs import RoomBlackCount, RoomConnectedBlack, LineBlackCount, NoWhiteAcrossThreeRooms
from puzzle_defs import RectangularComponents, NonRectangularComponents
from puzzle_defs import DistinctWhiteNumbers
from puzzle_defs import RunLengthLimit
from puzzle_defs import RoomRotationalSymmetry
from puzzle_defs import ColorComponentSize
from puzzle_defs import NoTouchingEqualTetrominoes
from puzzle_defs import WhiteVisibilityCounts
from puzzle_defs import ComponentsTouchBorder
from puzzle_defs import WhiteIslandAreas, WhiteAreaClues
from puzzle_defs import AdjacentBlackCounts
from puzzle_defs import ColorDegreeRange, ColorEndpointCount
from puzzle_defs import AdjacentBlackComponentSum
from puzzle_defs import UniformRooms, AcyclicColor, RoomFillLevels
from puzzle_defs import NoColorAcrossRooms, AdjacentRoomCountsDiffer
from puzzle_defs import RoomComponentCount, EqualRoomComponentSizes
from puzzle_defs import ComponentAreaClues
from puzzle_defs import CornerLinkedComponents, OneFalseAdjacentCountPerRoom, DirectionalRunLimit, RoomMajorityCount
from puzzle_defs import CornerConnectedColor, WhiteEndpointMarkers, AdjacentBlackRuns
from puzzle_defs.puzzles.shading import CLUE_KINDS, Clue, ShadingRule
from generate_shading import RULES, clue_record, rule_record
from shading_recipe import BUILT_IN_RULE_TYPES, rule_choices

BUILT_INS = BUILT_IN_RULE_TYPES
Bits = tuple[int, ...]


def _components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining, groups = set(cells), []
    while remaining:
        group: set[tuple[int, int]] = set()
        todo = [min(remaining)]
        while todo:
            r, c = todo.pop()
            if (r, c) in remaining:
                remaining.remove((r, c))
                group.add((r, c))
                todo.extend(v for v in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)) if v in remaining)
        groups.append(group)
    return groups


def accepts(rule: ShadingRule, bits: Bits, rows: int, cols: int) -> bool:
    """A finite checker independent of the constraint encoding, not a new DSL."""
    black = {(r, c) for r in range(rows) for c in range(cols) if bits[r * cols + c]}
    if type(rule) is BlackCount:
        return len(black) == rule.count
    if type(rule) is RoomMajorityCount:
        for label in {n for row in rule.rooms for n in row}:
            values = [bits[r*cols+c] for r in range(rows) for c in range(cols) if rule.rooms[r][c] == label]
            if max(values.count(0),values.count(1)) != rule.count:
                return False
        return True
    if type(rule) is DirectionalRunLimit:
        lines = [(bits[r*cols:(r+1)*cols],int(not rule.horizontal_black)) for r in range(rows)]
        lines += [(bits[c::cols],int(rule.horizontal_black)) for c in range(cols)]
        return all(color != target or sum(1 for _ in run) <= rule.max_length
                   for line,target in lines for color,run in groupby(line))
    if type(rule) is OneFalseAdjacentCountPerRoom:
        errors = {n:0 for row in rule.rooms for n in row}
        for r in range(rows):
            for c in range(cols):
                count = rule.neighbor_counts[r][c]
                if count is None:
                    continue
                if (r,c) in black:
                    return False
                actual = sum(abs(r-s)+abs(c-t) == 1 for s,t in black)
                errors[rule.rooms[r][c]] += actual != count
        return all(n == 1 for n in errors.values())
    if type(rule) is CornerLinkedComponents:
        selected = {(r,c) for r in range(rows) for c in range(cols) if (((r,c) in black) == rule.black)}
        remaining = set(selected)
        while remaining:
            group,pending = set(),[min(remaining)]
            while pending:
                r,c = pending.pop()
                if (r,c) not in remaining:
                    continue
                remaining.remove((r,c));group.add((r,c))
                pending.extend([(r-1,c),(r+1,c),(r,c-1),(r,c+1)])
            if not any((r+dr,c+dc) in selected-group for r,c in group for dr in (-1,1) for dc in (-1,1)):
                return False
        return True
    if type(rule) is ComponentAreaClues:
        for r in range(rows):
            for c in range(cols):
                area = rule.component_areas[r][c]
                if not area:
                    continue
                color = (r,c) in black
                seen,pending = set(),[(r,c)]
                while pending:
                    s,t = pending.pop()
                    if ((s,t) in seen or not 0 <= s < rows or not 0 <= t < cols
                            or (((s,t) in black) != color)):
                        continue
                    seen.add((s,t));pending.extend([(s-1,t),(s+1,t),(s,t-1),(s,t+1)])
                if len(seen) != area:
                    return False
        return True
    if type(rule) is RoomComponentCount or type(rule) is EqualRoomComponentSizes:
        for label in {n for row in rule.rooms for n in row}:
            remaining = {(r,c) for r in range(rows) for c in range(cols)
                         if rule.rooms[r][c] == label and (((r,c) in black) == rule.black)}
            sizes = []
            while remaining:
                group,pending = set(),[min(remaining)]
                while pending:
                    r,c = pending.pop()
                    if (r,c) not in remaining:
                        continue
                    remaining.remove((r,c));group.add((r,c))
                    pending.extend([(r-1,c),(r+1,c),(r,c-1),(r,c+1)])
                sizes.append(len(group))
            if type(rule) is RoomComponentCount and len(sizes) != rule.count:
                return False
            if type(rule) is EqualRoomComponentSizes and len(set(sizes)) > 1:
                return False
        return True
    if type(rule) is NoColorAcrossRooms:
        selected = [(r,c) for r in range(rows) for c in range(cols) if ((r,c) in black) == rule.black]
        return not any(abs(r-s)+abs(c-t) == 1 and rule.rooms[r][c] != rule.rooms[s][t]
                       for r,c in selected for s,t in selected)
    if type(rule) is AdjacentRoomCountsDiffer:
        members = {}
        for r in range(rows):
            for c in range(cols):
                members.setdefault(rule.rooms[r][c],set()).add((r,c))
        sizes = {label:sum((p in black) == rule.black for p in cells) for label,cells in members.items()}
        return not any(sizes[a] == sizes[b] and any(abs(r-s)+abs(c-t) == 1
                       for r,c in members[a] for s,t in members[b])
                       for a in members for b in members if a < b)
    if type(rule) is RoomFillLevels:
        # Every selected cell requires all same-room cells at its height or
        # lower, without relying on the encoder's row representatives/chain.
        cells = [(r,c) for r in range(rows) for c in range(cols)]
        for r,c in cells:
            if ((r,c) in black) != rule.black:
                continue
            if any((((s,t) in black) != rule.black) for s,t in cells
                   if s >= r and rule.rooms[s][t] == rule.rooms[r][c]):
                return False
        return True
    if type(rule) is AdjacentBlackRuns:
        for r in range(rows):
            for c in range(cols):
                clue = rule.run_clues[r][c]
                if clue is None:
                    continue
                if (r,c) in black:
                    return False
                # Build components of occupied positions in a fixed eight-cycle,
                # including outside positions as unoccupied separating gaps.
                coords = [(r-1,c),(r-1,c+1),(r,c+1),(r+1,c+1),(r+1,c),(r+1,c-1),(r,c-1),(r-1,c-1)]
                remaining = {i for i,p in enumerate(coords) if p in black}
                sizes = []
                while remaining:
                    pending,group = [min(remaining)],set()
                    while pending:
                        i = pending.pop()
                        if i not in remaining:
                            continue
                        remaining.remove(i); group.add(i)
                        pending.extend([(i-1)%8,(i+1)%8])
                    sizes.append(len(group))
                if tuple(sorted(sizes)) != (() if clue == (0,) else clue):
                    return False
        return True
    if type(rule) is WhiteEndpointMarkers:
        for r in range(rows):
            for c in range(cols):
                white_degree = sum(0 <= s < rows and 0 <= t < cols and (s,t) not in black
                                   for s,t in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)))
                endpoint = (r,c) not in black and white_degree == 1
                if endpoint != bool(rule.markers[r][c]):
                    return False
        return True
    if type(rule) is CornerConnectedColor:
        selected = black if rule.black else {(r,c) for r in range(rows) for c in range(cols)} - black
        if not selected:
            return not rule.nonempty
        reached, todo = set(), [min(selected)]
        while todo:
            p = todo.pop()
            if p in reached:
                continue
            reached.add(p)
            todo.extend(q for q in selected - reached if max(abs(p[0]-q[0]),abs(p[1]-q[1])) == 1)
        return reached == selected
    if type(rule) is UniformRooms:
        return all(len({bits[r*cols+c] for r in range(rows) for c in range(cols) if rule.rooms[r][c] == label}) == 1
                   for label in {n for row in rule.rooms for n in row})
    if type(rule) is AcyclicColor:
        selected = black if rule.black else {(r,c) for r in range(rows) for c in range(cols)} - black
        # For every connected component, a simple undirected graph is a tree
        # exactly when its edge count is its vertex count minus one.
        return all(sum((r+1,c) in group for r,c in group) + sum((r,c+1) in group for r,c in group) == len(group)-1
                   for group in _components(selected))
    if type(rule) is AdjacentBlackComponentSum:
        groups = _components(black)
        for r in range(rows):
            for c in range(cols):
                count = rule.component_counts[r][c]
                if count is None:
                    continue
                neighbors = {(r-1,c),(r+1,c),(r,c-1),(r,c+1)}
                if (r,c) in black or sum(len(g) for g in groups if g & neighbors) != count:
                    return False
        return True
    if type(rule) is ColorDegreeRange or type(rule) is ColorEndpointCount:
        selected = black if rule.black else {(r,c) for r in range(rows) for c in range(cols)} - black
        degrees = [sum(abs(r-s)+abs(c-t) == 1 for s,t in selected) for r,c in selected]
        if type(rule) is ColorDegreeRange:
            return all(rule.minimum <= n <= rule.maximum for n in degrees)
        return degrees.count(1) == rule.count
    if type(rule) is AdjacentBlackCounts:
        for r in range(rows):
            for c in range(cols):
                count = rule.neighbor_counts[r][c]
                if count is None:
                    continue
                adjacent = sum((max(abs(r-s),abs(c-t)) if rule.diagonal else abs(r-s)+abs(c-t)) == 1 for s,t in black)
                if (r,c) in black or adjacent != count:
                    return False
        return True
    if type(rule) is WhiteIslandAreas or type(rule) is WhiteAreaClues:
        numbers = {(r,c): rule.areas[r][c] for r in range(rows) for c in range(cols) if rule.areas[r][c] > 0}
        if black.intersection(numbers):
            return False
        white = {(r,c) for r in range(rows) for c in range(cols)} - black
        for group in _components(white):
            labels = [numbers[c] for c in group if c in numbers]
            if len(labels) > 1 or labels and labels[0] != len(group) or not labels and type(rule) is WhiteIslandAreas:
                return False
        return True
    if type(rule) is ComponentsTouchBorder:
        chosen = black if rule.black else {(r,c) for r in range(rows) for c in range(cols)} - black
        return all(any(r in (0,rows-1) or c in (0,cols-1) for r,c in group) for group in _components(chosen))
    if type(rule) is WhiteVisibilityCounts:
        for r in range(rows):
            for c in range(cols):
                count = rule.counts[r][c]
                if not count:
                    continue
                if (r, c) in black:
                    return False
                visible = 1
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    s, t = r + dr, c + dc
                    while 0 <= s < rows and 0 <= t < cols and (s, t) not in black:
                        visible += 1
                        s, t = s + dr, t + dc
                if visible != count:
                    return False
        return True
    if type(rule) is DistinctWhiteNumbers:
        lines = [[(r,c) for c in range(cols)] for r in range(rows)] + [[(r,c) for r in range(rows)] for c in range(cols)]
        for line in lines:
            remaining = [rule.numbers[r][c] for r,c in line if (r,c) not in black]
            if len(remaining) != len(set(remaining)): return False
        return True
    if type(rule) is NonTouchingBlack:
        return not any((max(abs(r-s), abs(c-t)) if rule.diagonal else abs(r-s)+abs(c-t)) == 1
                       for (r, c), (s, t) in combinations(black, 2))
    if type(rule) is ConnectedWhite or type(rule) is ConnectedBlack:
        cells = black if type(rule) is ConnectedBlack else {(r, c) for r in range(rows) for c in range(cols)} - black
        return len(_components(cells)) <= 1 and (bool(cells) or not rule.nonempty)
    if type(rule) is NoWhite2x2:
        return all(any((r+dr, c+dc) in black for dr in (0, 1) for dc in (0, 1))
                   for r in range(rows-1) for c in range(cols-1))
    if type(rule) is NoBlack2x2:
        return all(any((r+dr, c+dc) not in black for dr in (0, 1) for dc in (0, 1))
                   for r in range(rows-1) for c in range(cols-1))
    if type(rule) is BlackDominoes:
        return all(len(group) == 2 for group in _components(black))
    if type(rule) is NoTouchingEqualTetrominoes:
        pieces = []
        for label in {n for row in rule.rooms for n in row}:
            selected = {(r,c) for r,c in black if rule.rooms[r][c] == label}
            if len(selected) == 4 and len(_components(selected)) == 1:
                pieces.append(selected)
        for a,b in combinations(pieces,2):
            if any(abs(r-s)+abs(c-t) == 1 for r,c in a for s,t in b) and _congruent(a,b):
                return False
        return True
    if type(rule) is ColorComponentSize:
        selected = black if rule.black else {(r,c) for r in range(rows) for c in range(cols)} - black
        return all(len(group) == rule.size for group in _components(selected))
    if type(rule) is RoomRotationalSymmetry:
        for label in {n for row in rule.rooms for n in row}:
            members = {(r,c) for r in range(rows) for c in range(cols) if rule.rooms[r][c] == label}
            selected = black & members
            # Compare sets after rotation, independently of encoded cell equalities.
            row_sum = min(r for r,c in members) + max(r for r,c in members)
            col_sum = min(c for r,c in members) + max(c for r,c in members)
            if {(row_sum-r,col_sum-c) for r,c in selected} != selected:
                return False
        return True
    if type(rule) is RectangularComponents or type(rule) is NonRectangularComponents:
        selected = black if rule.black else {(r, c) for r in range(rows) for c in range(cols)} - black
        # Independent of the DSL's local corners / isolated-rectangle clauses:
        # compare every component's size to its axis-aligned bounding box area.
        def rectangle(group: set[tuple[int, int]]) -> bool:
            height = max(r for r, _ in group) - min(r for r, _ in group) + 1
            width = max(c for _, c in group) - min(c for _, c in group) + 1
            return len(group) == height * width
        return all(rectangle(group) == (type(rule) is RectangularComponents) for group in _components(selected))
    if type(rule) is RoomBlackCount or type(rule) is RoomConnectedBlack:
        for label in {n for row in rule.rooms for n in row}:
            selected = {(r, c) for r, c in black if rule.rooms[r][c] == label}
            if type(rule) is RoomBlackCount:
                if len(selected) != rule.count:
                    return False
            elif len(_components(selected)) > 1 or not selected and rule.nonempty:
                return False
        return True
    if type(rule) is NoWhiteAcrossThreeRooms:
        # Scan maximal white runs and count room entries, independently of the
        # encoder's minimal intervals between consecutive boundary positions.
        lines = [[(r,c) for c in range(cols)] for r in range(rows)] + [[(r,c) for r in range(rows)] for c in range(cols)]
        for line in lines:
            previous, segments = None, 0
            for r,c in line:
                if (r,c) in black:
                    previous, segments = None, 0
                else:
                    label = rule.rooms[r][c]
                    if label != previous:
                        segments += 1
                    if segments >= 3:
                        return False
                    previous = label
        return True
    row_lines = [bits[r*cols:(r+1)*cols] for r in range(rows)]
    col_lines = [bits[c::cols] for c in range(cols)]
    if type(rule) is RunLengthLimit:
        return all(sum(1 for _ in group) <= rule.max_length
                   for line in row_lines + col_lines for _,group in groupby(line))
    if type(rule) is NoThreeConsecutive:
        return all(len(set(line[i:i+3])) > 1 for line in row_lines + col_lines for i in range(len(line)-2))
    if type(rule) is BalancedLines:
        return all(line.count(0) == line.count(1) for line in row_lines + col_lines)
    if type(rule) is DistinctLines:
        return len(set(row_lines)) == rows and len(set(col_lines)) == cols
    if type(rule) is LineBlackCount:
        return all(sum(line) == rule.count for line in row_lines + col_lines)
    raise ValueError("Diagnostics support exact built-in rule types only, not custom rules or subclasses")


def _congruent(first: set[tuple[int,int]], second: set[tuple[int,int]]) -> bool:
    """Independent signed-axis transforms, not polyomino variants or piece names."""
    def origin(points):
        low_r,low_c = min(r for r,c in points),min(c for r,c in points)
        return {(r-low_r,c-low_c) for r,c in points}
    target = origin(second)
    return any(origin({(sr*(c if swap else r),sc*(r if swap else c)) for r,c in first}) == target
               for swap in (False,True) for sr in (-1,1) for sc in (-1,1))


def full_clues(recipe: ShadingRecipe, bits: Bits) -> tuple[Clue, ...]:
    clues: list[Clue] = []
    for kind in recipe.clue_kinds:
        if kind == "cell":
            clues.extend((Cell(r, c), bits[r*recipe.cols+c])
                         for r in range(recipe.rows) for c in range(recipe.cols))
        elif kind == "row-count":
            clues.extend(RowCountClue(r, sum(bits[r*recipe.cols:(r+1)*recipe.cols]))
                         for r in range(recipe.rows))
        else:
            clues.extend(ColumnCountClue(c, sum(bits[r*recipe.cols+c] for r in range(recipe.rows)))
                         for c in range(recipe.cols))
    return tuple(clues)


def finite_space(recipe: ShadingRecipe) -> tuple[ShadingPuzzle, list[Bits], list[set[int]]]:
    """Validate once and cache which finite boards satisfy each rule occurrence."""
    if type(recipe) is not ShadingRecipe:
        raise ValueError("Finite diagnostics require an exact ShadingRecipe; composed recipes and subclasses are unsupported")
    if recipe.rows * recipe.cols > 9 or len(recipe.rules) > 8:
        raise ValueError("Diagnostics support at most 9 cells and 8 rule occurrences")
    if any(type(rule) not in BUILT_INS for rule in recipe.rules):
        raise ValueError("Diagnostics support exact built-in rule types only, not custom rules or subclasses")
    # Validate the recipe with the real builder, including count <= area.
    puzzle = recipe.create_empty()
    boards = list(product([0, 1], repeat=recipe.rows * recipe.cols))
    masks = [{i for i, bits in enumerate(boards) if accepts(rule, bits, recipe.rows, recipe.cols)}
             for rule in recipe.rules]
    return puzzle, boards, masks


def analyze(recipe: ShadingRecipe, *, seed_start: int = 0, seed_count: int = 0) -> dict[str, Any]:
    puzzle, boards, masks = finite_space(recipe)
    if (type(seed_count) is not int or not 0 <= seed_count <= 32
            or type(seed_start) is not int or not 0 <= seed_start <= 2**31 - max(seed_count, 1)):
        raise ValueError("Use 0..32 seeds, all between 0 and 2147483647")

    def allowed(indices: Iterable[int]) -> set[int]:
        result = set(range(len(boards)))
        for index in indices:
            result.intersection_update(masks[index])
        return result

    valid = allowed(range(len(recipe.rules)))
    conflicts: list[tuple[int, ...]] = []
    if not valid:
        for size in range(1, len(recipe.rules)+1):
            for indices in combinations(range(len(recipe.rules)), size):
                if not any(set(core) <= set(indices) for core in conflicts) and not allowed(indices):
                    conflicts.append(indices)
    groups: dict[tuple[Clue, ...], list[Bits]] = {}
    for index in sorted(valid):
        bits = boards[index]
        groups.setdefault(full_clues(recipe, bits), []).append(bits)
    identifiable = sum(len(group) == 1 for group in groups.values())
    policy = ("no_completion" if not valid else "none_identifiable" if not identifiable
              else "all_identifiable" if identifiable == len(valid) else "some_identifiable")

    def grid(bits: Bits) -> list[list[int]]:
        return [list(bits[r*recipe.cols:(r+1)*recipe.cols]) for r in range(recipe.rows)]

    ambiguity = next(({"clues": [clue_record(c) for c in clues], "answer_count": len(group),
                       "witnesses": [grid(bits) for bits in group[:2]]}
                      for clues, group in groups.items() if len(group) > 1), None)
    attempts = []
    observed: dict[Bits, int] = {}
    for seed in range(seed_start, seed_start+seed_count) if valid else ():
        solution = puzzle.solve(seed=seed)
        if solution is None:
            raise RuntimeError("Solver returned no completion despite the finite checker finding one")
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        if bits not in groups.get(full_clues(recipe, bits), []):
            raise RuntimeError("Solver completion disagrees with the finite rule checker")
        actual_clues = tuple(recipe.extract_clues(solution, puzzle))
        if actual_clues != full_clues(recipe, bits):
            raise RuntimeError("Extracted clues disagree with the finite clue checker")
        answer_id = observed.setdefault(bits, len(observed)+1)
        attempts.append({"seed": seed, "answer_id": answer_id,
                         "answers_with_same_full_clues": len(groups[actual_clues])})
    return {
        "format": "puzzle-box/shading-analysis-v1", "rows": recipe.rows, "cols": recipe.cols,
        "rules": [rule_record(r) for r in recipe.rules], "clue_kinds": list(recipe.clue_kinds),
        "enumerated_boards": len(boards), "completion_count": len(valid),
        "minimal_conflicts": [[i+1 for i in core] for core in conflicts],
        "hint_policy": policy, "full_clue_groups": len(groups),
        "identifiable_completions": identifiable, "ambiguous_completions": len(valid)-identifiable,
        "ambiguous_example": ambiguity,
        "seed_probe": {"start": seed_start, "requested": seed_count, "attempts": attempts,
                       "distinct_completions": len(observed),
                       "identifiable_attempts": sum(a["answers_with_same_full_clues"] == 1 for a in attempts),
                       "observed_answers": [grid(bits) for bits in observed]},
        "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                        "seeded_search_workers": 1},
    }


def explain(report: dict[str, Any]) -> str:
    total, eligible = report["completion_count"], report["identifiable_completions"]
    lines = [f"Shading recipe: {report['rows']} rows x {report['cols']} columns",
             f"Exhaustively checked {report['enumerated_boards']} black/white boards.",
             f"Visible completions: {total}.", "Rules (1-based indices):"]
    lines.extend(f"  {i}: {json.dumps(rule, sort_keys=True)}" for i, rule in enumerate(report["rules"], 1))
    if not total:
        lines.append("No completion satisfies these rules. Changing seeds or clues cannot fix this recipe.")
        for conflict in report["minimal_conflicts"]:
            lines.append(f"  Conflicting rule indices: {conflict}; removing any one makes this subset feasible.")
    else:
        lines.append(f"Full candidate hints identify {eligible} of {total} completions uniquely.")
        if not eligible:
            lines.append("No seed can make this hint policy unique; change hints or rules.")
        elif eligible < total:
            lines.append("Some completions need additional hints; another seed may help, without a success guarantee.")
        else:
            lines.append("Every completion can be identified by this full candidate hint pool.")
        if (example := report["ambiguous_example"]) is not None:
            lines.append(f"Two different answers share these full clues ({example['answer_count']} answers total):")
            lines.append("  " + json.dumps(example["clues"], sort_keys=True))
            lines.extend("  " + "/".join("".join("#" if v else "." for v in row) for row in board)
                         for board in example["witnesses"])
    probe = report["seed_probe"]
    if probe["requested"] and not total:
        lines.append("Seed probe skipped because the rule set has no completion.")
    elif probe["requested"]:
        lines.append(f"Seed probe: {len(probe['attempts'])} solved, {probe['distinct_completions']} distinct answers, "
                     f"{probe['identifiable_attempts']} with uniquely identifying full hints.")
        lines.append("Observed diversity is not a sampling probability or human-difficulty estimate; symmetries count separately.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--rules", nargs="*", choices=RULES, default=["count", "non-touching"])
    parser.add_argument("--hints", nargs="*", choices=CLUE_KINDS, default=["row-count", "column-count"])
    parser.add_argument("--black-count", type=int, default=2)
    parser.add_argument("--diagonal", action="store_true")
    parser.add_argument("--allow-empty-white", action="store_true")
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--seed-count", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Print the full report, including witness answers")
    parser.add_argument("--output", type=Path, help="Save the JSON report (includes witness answers)")
    args = parser.parse_args()
    try:
        choices = rule_choices(count=args.black_count, diagonal=args.diagonal, allow_empty_white=args.allow_empty_white)
        recipe = ShadingRecipe(args.rows, args.cols, tuple(choices[r] for r in args.rules), tuple(args.hints))
        report = analyze(recipe, seed_start=args.seed_start, seed_count=args.seed_count)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded if args.json else explain(report), end="" if args.json else "\n")
        return 0  # Diagnosed contradictions/ambiguity are results, not input errors.
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
