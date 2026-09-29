import pytest

from poly.geometry import (
    PolygonDraft, distance, landmarks_to_pixels, order_around_centroid, point_in_polygon,
    ZoneMapper, order_corners, quick_zone, translate_within,
)

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


def test_draft_rejects_vertex_on_top_of_any_earlier_vertex():
    draft = PolygonDraft()
    for v in [(0, 0), (100, 0), (100, 100)]:
        draft.add_vertex(v, 15)
    assert not draft.add_vertex((5, 5), min_distance=15)  # near the first, not the last


def _rotations(seq):
    return [seq[i:] + seq[:i] for i in range(len(seq))]


def test_order_around_centroid_untangles_any_order():
    corners = [(0, 0), (100, 0), (100, 100), (0, 100)]  # clockwise on screen
    bow_tie = [(0, 0), (100, 100), (100, 0), (0, 100)]
    assert order_around_centroid(bow_tie) in _rotations(corners)


def test_order_around_centroid_keeps_an_inner_point_as_a_notch():
    pts = [(0, 0), (100, 0), (100, 100), (0, 100), (50, 20)]
    ordered = order_around_centroid(pts)
    assert sorted(ordered) == sorted(pts)
    assert not point_in_polygon((50, 10), ordered)  # carved out by the notch
    assert point_in_polygon((50, 60), ordered)


def test_order_around_centroid_leaves_tiny_inputs_alone():
    assert order_around_centroid([(1, 2), (3, 4)]) == [(1, 2), (3, 4)]


def test_close_reorders_vertices():
    draft = PolygonDraft(vertices=[(0, 0), (100, 100), (100, 0), (0, 100)])
    assert draft.close(3)
    assert draft.contains((50, 50))
    assert draft.contains((90, 50))  # a bow-tie would leave this outside


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


def test_quick_zone_centred_when_it_fits():
    assert quick_zone((320, 200), 200, 100, (640, 480), None, 10) == [
        (220, 150), (420, 150), (420, 250), (220, 250)]


def test_quick_zone_pushed_inside_the_frame():
    rect = quick_zone((20, 20), 200, 100, (640, 480), None, 10)
    assert rect[0] == (10, 10) and rect[2] == (210, 110)


def test_quick_zone_lifted_above_bottom_limit():
    rect = quick_zone((320, 400), 200, 100, (640, 480), 300, 10)
    assert rect[2][1] == 300 and rect[0][1] == 200


def test_quick_zone_shortened_when_it_cannot_fit():
    rect = quick_zone((320, 100), 200, 400, (640, 480), 200, 10)
    assert rect[0][1] == 10 and rect[2][1] == 200


def test_translate_within_moves_freely_inside():
    sq = [(100, 100), (200, 100), (200, 200), (100, 200)]
    assert translate_within(sq, 10.4, -20, (640, 480), 10)[0] == (110, 80)


def test_translate_within_stops_at_the_edges():
    sq = [(100, 100), (200, 100), (200, 200), (100, 200)]
    moved = translate_within(sq, -500, 1000, (640, 480), 10)
    assert min(v[0] for v in moved) == 10 and max(v[1] for v in moved) == 470


# ------------------------------------------------------------ zone -> screen mapping

SCREEN = (1920, 1080)
RECT = [(100, 100), (300, 100), (300, 250), (100, 250)]
# A skewed 4-sided zone, like one traced by hand: narrower at the top.
TRAPEZOID = [(140, 100), (260, 110), (320, 260), (90, 250)]


def mapper(vertices, padding=0.0):
    return ZoneMapper(vertices, SCREEN, padding)


def test_order_corners_starts_top_left_and_goes_clockwise():
    scrambled = [RECT[2], RECT[0], RECT[3], RECT[1]]
    assert order_corners(scrambled) == RECT


def test_rectangle_corners_map_to_screen_corners():
    m = mapper(RECT)
    assert m.uses_perspective
    assert [m.map(c) for c in RECT] == [(0, 0), (1919, 0), (1919, 1079), (0, 1079)]


def near(a, b, tol=1):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def test_rectangle_centre_maps_to_screen_centre():
    # The exact centre is (959.5, 539.5), so either neighbouring pixel is right.
    assert near(mapper(RECT).map((200, 175)), (960, 540))


@pytest.mark.parametrize("outside", [(99, 175), (301, 175), (200, 99), (200, 251), (0, 0)])
def test_outside_points_do_not_move_the_cursor(outside):
    assert mapper(RECT).map(outside) is None


def test_skewed_zone_still_fills_the_whole_screen():
    # The point of the perspective transform: every corner of a skewed zone
    # reaches the matching screen corner...
    m = mapper(TRAPEZOID)
    assert m.uses_perspective
    assert [m.map(c) for c in TRAPEZOID] == [(0, 0), (1919, 0), (1919, 1079), (0, 1079)]
    # ...points along an edge stay on that screen edge...
    left_mid = ((140 + 90) / 2, (100 + 250) / 2)
    assert m.map(left_mid)[0] == 0
    # ...and where the diagonals cross is the screen centre.
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = TRAPEZOID
    d = (x1 - x3) * (y2 - y4) - (y1 - y3) * (x2 - x4)
    t = ((x1 - x2) * (y2 - y4) - (y1 - y2) * (x2 - x4)) / d
    crossing = (x1 + t * (x3 - x1), y1 + t * (y3 - y1))
    assert near(m.map(crossing), (960, 540))


def test_vertex_order_does_not_matter():
    shuffled = [TRAPEZOID[3], TRAPEZOID[1], TRAPEZOID[0], TRAPEZOID[2]]
    assert mapper(shuffled).map(TRAPEZOID[0]) == (0, 0)


def test_other_shapes_use_the_bounding_box():
    pentagon = [(100, 100), (300, 100), (320, 200), (200, 260), (80, 200)]
    m = mapper(pentagon)
    assert not m.uses_perspective
    assert m.map((200, 180)) == (round((200 - 80) / 240 * 1919), round(80 / 160 * 1079))


def test_concave_four_sided_zone_falls_back_to_bounding_box():
    dart = [(100, 100), (200, 180), (300, 100), (200, 300)]
    assert not mapper(dart).uses_perspective


def test_edge_padding_makes_edges_easy_to_reach():
    m = mapper(RECT, padding=0.1)
    # 5% in from the left edge is inside the padding strip: already at the edge.
    assert m.map((110, 175))[0] == 0
    assert m.map((290, 240)) == (1919, 1079)
    assert near(m.map((200, 175)), (960, 540))  # centre unaffected
