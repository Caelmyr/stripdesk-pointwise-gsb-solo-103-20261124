"""Measured dark-band frame split suggestions.

The hand-tuned guides are evenly spaced, but uneven film transport can leave a
guide inside a picture.  This module proposes non-uniform internal edges that
still share the strip's first frame number, frame count and outer endpoints.

Hard requirements for an acceptable proposal:

* every internal edge lies inside one measured dark band and keeps at least one
  dark column on both sides;
* every native frame width is inside the operator's min/max width range.

Among all acceptable proposals the search first maximizes the smallest dark
band margin (columns spared on either side of an edge), then minimizes the total
movement away from the hand-adjusted guides so nearby pictures keep their plate
numbers.  Equal movement keeps the smallest edge coordinates first, which makes
the result deterministic.
"""

from collections import deque

from image_lab.validation import Invalid, integer

from . import layout


def width_limits(config):
    """Width bounds, tolerating records saved before the limits existed."""
    pitch = config['pitch']
    minimum = config.get('frame_min', max(8, round(pitch * 0.9)))
    maximum = config.get('frame_max', max(minimum, round(pitch * 1.1)))
    return int(minimum), int(maximum)


def band_at(position, bands):
    """Return the measured band that can host ``position`` with margin to spare."""
    for band in bands:
        if band['left'] < position < band['right']:
            return band
    return None


def eligible_positions(bands, start, stop):
    """Sorted unique columns strictly inside a measured band within the strip."""
    positions = set()
    for band in bands:
        left = max(start + 1, band['left'] + 1)
        right = min(stop - 1, band['right'] - 1)
        if left <= right:
            positions.update(range(left, right + 1))
    return sorted(positions)


def build_layers(count, positions, bands, start, stop):
    """One candidate map per edge: start, the internal edges, then the end."""
    layers = [{start: 0}]
    for _ in range(count - 1):
        layer = {}
        for position in positions:
            band = band_at(position, bands)
            if band is not None and start < position < stop:
                layer[position] = min(position - band['left'], band['right'] - position)
        layers.append(layer)
    layers.append({stop: 0})
    return layers


def reachable(margin, layers, width_min, width_max):
    """Layer-by-layer reachability with a sliding window over prior edges."""
    reach = [next(iter(layers[0]))]
    for layer in layers[1:-1]:
        ordered = sorted(layer)
        window = deque()
        index = 0
        current = []
        for position in ordered:
            if layer[position] < margin:
                continue
            lo, hi = position - width_max, position - width_min
            while index < len(reach) and reach[index] <= hi:
                # Strictly worse entries leave; equal cost keeps the smaller edge.
                while window and reach[window[-1]] > reach[index]:
                    window.pop()
                window.append(index)
                index += 1
            while window and reach[window[0]] < lo:
                window.popleft()
            if window:
                current.append(position)
        if not current:
            return None
        reach = current
    end = next(iter(layers[-1]))
    lo, hi = end - width_max, end - width_min
    return reach if any(lo <= position <= hi for position in reach) else None


def cheapest_path(margin, layers, width_min, width_max, guides):
    """Minimum total guide movement under the margin and width constraints."""
    costs = {next(iter(layers[0])): 0}
    pointers = {}
    for layer_index, layer in enumerate(layers[1:-1], start=1):
        ordered = sorted(costs)
        previous = [costs[position] for position in ordered]
        window = deque()
        index = 0
        next_costs = {}
        guide = guides[layer_index - 1]
        for position in sorted(layer):
            if layer[position] < margin:
                continue
            lo, hi = position - width_max, position - width_min
            while index < len(ordered) and ordered[index] <= hi:
                # On equal accumulated cost keep the smaller prior edge first.
                while window and previous[window[-1]] > previous[index]:
                    window.pop()
                window.append(index)
                index += 1
            while window and ordered[window[0]] < lo:
                window.popleft()
            if window:
                best = window[0]
                next_costs[position] = previous[best] + abs(position - guide)
                pointers[(layer_index, position)] = ordered[best]
        if not next_costs:
            return None
        costs = next_costs
    end = next(iter(layers[-1]))
    ordered = sorted(costs)
    previous = [costs[position] for position in ordered]
    window = deque()
    lo, hi = end - width_max, end - width_min
    for index, position in enumerate(ordered):
        if lo <= position <= hi:
            while window and previous[window[-1]] > previous[index]:
                window.pop()
            window.append(index)
    if not window:
        return None
    best = window[0]
    pointers[(len(layers) - 1, end)] = ordered[best]
    edges = [end]
    for layer_index in range(len(layers) - 1, 0, -1):
        edges.append(pointers[(layer_index, edges[-1])])
    edges.reverse()
    return edges, costs[ordered[best]]


def suggest(source, config, profile=None):
    """Return the best acceptable proposal, or ``feasible: false`` with reasons."""
    count = config['count']
    start = config['origin']
    stop = start + config['pitch'] * count
    width_min, width_max = width_limits(config)
    if profile is None:
        profile = layout.inspect_columns(source, config)
    bands = profile['bands']
    regular = layout.regular_frames(config)
    guides = [frame['left'] for frame in regular[1:]]
    span = stop - start

    if count == 1:
        feasible = width_min <= span <= width_max
        reasons = [] if feasible else [
            f'唯一一格原片宽度 {span} px 不在 {width_min}–{width_max} px 之间。']
        return {
            'feasible': feasible, 'edges': [start, stop],
            'min_margin': None, 'total_movement': 0, 'movements': [],
            'frames': regular, 'limits': [width_min, width_max], 'reasons': reasons,
        }

    positions = eligible_positions(bands, start, stop)
    layers = build_layers(count, positions, bands, start, stop)
    max_margin = max((layer[position] for layer in layers[1:-1] for position in layer),
                     default=0)
    chosen_margin = 0
    low, high = 1, max_margin
    while low <= high:
        middle = (low + high) // 2
        if reachable(middle, layers, width_min, width_max) is not None:
            chosen_margin = middle
            low = middle + 1
        else:
            high = middle - 1

    path = cheapest_path(chosen_margin, layers, width_min, width_max, guides)
    if path is None:
        reasons = []
        if width_min * count > span:
            reasons.append(f'最小原片宽度 {width_min} px × {count} 格超过片条跨度 {span} px。')
        if len(positions) < count - 1:
            reasons.append('实测暗带里能让两侧都留出一列的内线位置不足。')
        if not reasons:
            reasons.append('暗带位置与每格宽度限制凑不出一套完整分帧。')
        return {
            'feasible': False, 'edges': None, 'min_margin': None,
            'total_movement': None, 'movements': None, 'frames': None,
            'limits': [width_min, width_max], 'reasons': reasons,
        }
    edges, total_movement = path

    movements = [abs(edges[index] - guides[index - 1]) for index in range(1, count)]
    frames = [{
        'number': config['first'] + index,
        'left': edges[index], 'right': edges[index + 1],
        'width': edges[index + 1] - edges[index],
        'band_margin': None if index == 0 else layers[index][edges[index]],
    } for index in range(count)]
    return {
        'feasible': True, 'edges': edges, 'min_margin': chosen_margin,
        'total_movement': total_movement, 'movements': movements,
        'frames': frames, 'limits': [width_min, width_max], 'reasons': [],
    }


def validate_edges(edges, config, bands):
    """Re-check an adoption request against geometry, bands and width limits."""
    count = config['count']
    start = config['origin']
    stop = start + config['pitch'] * count
    if not isinstance(edges, list) or len(edges) != count + 1:
        raise Invalid('分帧边线数量需要与张数加一相符。')
    cleaned = [integer(value, '分帧边线', 0, config['origin'] + config['pitch'] * count)
               for value in edges]
    if cleaned[0] != start or cleaned[-1] != stop:
        raise Invalid('分帧建议必须沿用片条当前的左右端点。')
    if any(cleaned[index] >= cleaned[index + 1] for index in range(count)):
        raise Invalid('分帧边线必须从左到右严格递增。')
    width_min, width_max = width_limits(config)
    for index in range(count):
        width = cleaned[index + 1] - cleaned[index]
        if not width_min <= width <= width_max:
            raise Invalid(f'第 {index + 1} 格原片宽度 {width} px 超出 {width_min}–{width_max} px。')
    for position in cleaned[1:-1]:
        if band_at(position, bands) is None:
            raise Invalid(f'内线 {position} 不在实测暗带内，或暗带两侧没有各留一列。')
    return cleaned
