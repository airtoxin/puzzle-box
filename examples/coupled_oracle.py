"""Finite, solver-independent semantics for the small coupled-rule experiment."""

from itertools import product
from typing import Sequence

from puzzle import Cell, Edge, Vertex
from puzzle_defs import ArrowCountClue, BlackCellClue, EdgeStateClue, YajilinAnswer, YajilinRecipe
from puzzle_defs.puzzles.yajilin_recipe import YajilinClue, YajilinClueKind

RULES = ("coupling", "non_touching", "single_cycle")
HINTS: tuple[YajilinClueKind, ...] = ("arrow", "black", "edge")


def check_size(recipe: YajilinRecipe) -> None:
    if recipe.rows * recipe.cols > 8:
        raise ValueError("Coupled exploration supports at most 8 cells (both dimensions >= 2)")


def rule_names(mask: int) -> list[str]:
    if type(mask) is not int or not 0 <= mask < 8:
        raise ValueError("Rule mask must be an integer from 0 to 7")
    return [name for i, name in enumerate(RULES) if mask & (1 << i)]


def ordinary_cells(recipe: YajilinRecipe) -> tuple[Cell, ...]:
    check_size(recipe)
    blocked = {s.cell for s in recipe.arrow_sites}
    return tuple(Cell(r, c) for r in range(recipe.rows) for c in range(recipe.cols)
                 if Cell(r, c) not in blocked)


def edges(recipe: YajilinRecipe) -> tuple[Edge, ...]:
    check_size(recipe)
    # Geometry is independent of SquareGrid and the model's degree constraints.
    return tuple([Edge(Vertex(r, c), Vertex(r, c + 1))
                  for r in range(recipe.rows) for c in range(recipe.cols - 1)]
                 + [Edge(Vertex(r, c), Vertex(r + 1, c))
                    for r in range(recipe.rows - 1) for c in range(recipe.cols)])


def visited(loop: frozenset[Edge]) -> set[Cell]:
    return {Cell(*v) for e in loop for v in e}


def components(loop: frozenset[Edge]) -> int:
    neighbors: dict[Cell, set[Cell]] = {}
    for a, b in loop:
        neighbors.setdefault(Cell(*a), set()).add(Cell(*b))
        neighbors.setdefault(Cell(*b), set()).add(Cell(*a))
    unseen = set(neighbors)
    count = 0
    while unseen:
        todo = [min(unseen)]
        count += 1
        while todo:
            cell = todo.pop()
            if cell in unseen:
                unseen.remove(cell)
                todo.extend(neighbors[cell])
    return count


def answer_key(answer: YajilinAnswer) -> tuple:
    return tuple(sorted(answer.black_cells)), tuple(sorted(answer.loop_edges))


def universe(recipe: YajilinRecipe) -> tuple[YajilinAnswer, ...]:
    """All nonempty degree-0/2 edge sets avoiding arrows, times all black masks."""
    ordinary = ordinary_cells(recipe)
    candidates = edges(recipe)
    answers = []
    for bits in product((0, 1), repeat=len(candidates)):
        loop = frozenset(e for e, bit in zip(candidates, bits) if bit)
        degrees: dict[Cell, int] = {}
        for e in loop:
            for vertex in e:
                cell = Cell(*vertex)
                degrees[cell] = degrees.get(cell, 0) + 1
        if not degrees or set(degrees) - set(ordinary) or any(d != 2 for d in degrees.values()):
            continue
        for black_bits in product((0, 1), repeat=len(ordinary)):
            black = frozenset(c for c, bit in zip(ordinary, black_bits) if bit)
            answers.append(YajilinAnswer(black, loop))
    return tuple(sorted(answers, key=answer_key))


def accepts(recipe: YajilinRecipe, mask: int, answer: YajilinAnswer) -> bool:
    """Apply optional rules to an answer already in universe(recipe)."""
    rule_names(mask)
    if mask & 1 and answer.black_cells != set(ordinary_cells(recipe)) - visited(answer.loop_edges):
        return False
    if mask & 2 and any(abs(a.row - b.row) + abs(a.col - b.col) == 1
                        for a in answer.black_cells for b in answer.black_cells):
        return False
    return not mask & 4 or components(answer.loop_edges) == 1


def full_clues(recipe: YajilinRecipe, answer: YajilinAnswer,
               kinds: Sequence[YajilinClueKind]) -> tuple[YajilinClue, ...]:
    """All candidate clues of selected kinds, in canonical order; no reduction."""
    if len(set(kinds)) != len(kinds) or any(k not in HINTS for k in kinds):
        raise ValueError("Hint kinds must be distinct arrow, black or edge values")
    clues: list[YajilinClue] = []
    if "arrow" in kinds:
        for site in recipe.arrow_sites:
            r, c = site.cell
            # Independent of YajilinRecipe.ray(); arrow cells are never black.
            count = sum((site.direction == "up" and b.col == c and b.row < r)
                        or (site.direction == "down" and b.col == c and b.row > r)
                        or (site.direction == "left" and b.row == r and b.col < c)
                        or (site.direction == "right" and b.row == r and b.col > c)
                        for b in answer.black_cells)
            clues.append(ArrowCountClue(site.cell, count))
    if "black" in kinds:
        clues.extend(BlackCellClue(c, int(c in answer.black_cells)) for c in ordinary_cells(recipe))
    if "edge" in kinds:
        clues.extend(EdgeStateClue(e, int(e in answer.loop_edges)) for e in edges(recipe))
    return tuple(clues)


def groups(recipe: YajilinRecipe, answers: Sequence[YajilinAnswer],
           kinds: Sequence[YajilinClueKind]) -> dict[tuple[YajilinClue, ...], list[YajilinAnswer]]:
    result: dict[tuple[YajilinClue, ...], list[YajilinAnswer]] = {}
    for answer in answers:
        result.setdefault(full_clues(recipe, answer, kinds), []).append(answer)
    return result
