import pytest

from poly.geometry import PolygonDraft, distance, landmarks_to_pixels, point_in_polygon

SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


def test_landmarks_to_pixels_scales_z_by_width():
    assert landmarks_to_pixels([(0.5, 0.25, -0.1)], 640, 480) == [(320.0, 120.0, -64.0)]


def test_distance():
    assert distance((0, 0), (3, 4)) == pytest.approx(5.0)


@pytest.mark.parametrize("point, expected", [
    ((50, 50), True),     # centre
    ((100, 50), True),    # on an edge counts as inside
    ((0, 0), True),       # on a corner
    ((101, 50), False),   # just outside
    ((-5, -5), False),
    ((50.5, 99.9), True), # float coordinates are fine
])
def test_point_in_square(point, expected):
    assert point_in_polygon(point, SQUARE) is expected


def test_point_in_concave_polygon():
    # An "L" shape: the notch at the top right is outside.
    l_shape = [(0, 0), (50, 0), (50, 50), (100, 50), (100, 100), (0, 100)]
    assert point_in_polygon((25, 25), l_shape)
    assert not point_in_polygon((75, 25), l_shape)
    assert point_in_polygon((75, 75), l_shape)


def test_degenerate_polygon_contains_nothing():
    assert not point_in_polygon((0, 0), [])
    assert not point_in_polygon((5, 0), [(0, 0), (10, 0)])


def test_draft_rejects_vertex_too_close_to_previous():
    draft = PolygonDraft()
    assert draft.add_vertex((0, 0), min_distance=15)
    assert not draft.add_vertex((10, 0), min_distance=15)
    assert not draft.add_vertex((15, 0), min_distance=15)  # exactly at the limit
    assert draft.add_vertex((16, 0), min_distance=15)
    assert draft.vertices == [(0, 0), (16, 0)]


def test_draft_needs_min_vertices_to_close():
    draft = PolygonDraft()
    draft.add_vertex((0, 0), 15)
    draft.add_vertex((100, 0), 15)
    assert not draft.close(min_vertices=3)
    draft.add_vertex((100, 100), 15)
    assert draft.close(min_vertices=3)
    assert draft.closed
    assert not draft.close(min_vertices=3)  # already closed


def test_closed_draft_ignores_new_vertices():
    draft = PolygonDraft(vertices=list(SQUARE))
    draft.close(3)
    assert not draft.add_vertex((500, 500), 15)
    assert len(draft.vertices) == 4


def test_contains_only_once_closed():
    draft = PolygonDraft(vertices=list(SQUARE))
    assert not draft.contains((50, 50))
    draft.close(3)
    assert draft.contains((50, 50))
    assert not draft.contains((150, 50))


def test_reset_clears_everything():
    draft = PolygonDraft(vertices=list(SQUARE))
    draft.close(3)
    draft.reset()
    assert draft.vertices == []
    assert not draft.closed
