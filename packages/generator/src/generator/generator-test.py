from generator import generate, reduce_clues
from puzzle.constraints import UniqueConstraint


def test_generate_sudoku():
    from puzzle_defs import SudokuPuzzle

    clues = generate(SudokuPuzzle, seed=42)
    assert len(clues) > 0
    assert len(clues) < 81

    # Verify unique solution
    instance = SudokuPuzzle.build_from_clues(clues)
    instance.add(UniqueConstraint())
    sol = instance.solve()
    assert sol is not None

    # Verify solution is valid
    grid = instance.result(sol)
    for r in range(9):
        assert sorted(grid[r]) == list(range(1, 10))
    for c in range(9):
        assert sorted(grid[r][c] for r in range(9)) == list(range(1, 10))


def test_generate_sudoku_different_seeds():
    from puzzle_defs import SudokuPuzzle

    clues1 = generate(SudokuPuzzle, seed=1)
    clues2 = generate(SudokuPuzzle, seed=2)
    # Different seeds should produce different puzzles (with high probability)
    assert set(clues1) != set(clues2)


def test_reduce_clues_removes_some():
    from puzzle_defs import SudokuPuzzle

    empty = SudokuPuzzle.create_empty()
    sol = empty.solve(seed=42)
    all_clues = SudokuPuzzle.extract_clues(sol, empty)
    assert len(all_clues) == 81

    reduced = reduce_clues(SudokuPuzzle, all_clues, seed=42)
    assert len(reduced) < 81
    assert len(reduced) > 0
