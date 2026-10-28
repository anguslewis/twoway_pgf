from .diagnostics import trace as _log
from . import settings as _settings
import itertools
_LEGEND_SOLVE_PASSES = 24
_LEGEND_TOLERANCE_IN = 0.0005

# Maximum ink-bottom distance from a legend row's highest entry, in inches.
_ROW_CLUSTER_IN = 0.05
_HEIGHT_PASSES = 4
_HEIGHT_TOLERANCE_IN = 0.0005

def _inches(artist, fig):
    return artist.get_window_extent(renderer=fig.canvas.get_renderer()).transformed(fig.dpi_scale_trans.inverted())

def _y_title_extent_in(fig, ax):
    box = _inches(ax.yaxis.label, fig)
    return box.y1 - box.y0

def _wrap_y_title(fig, ax, layout, region_h_in):
    label = ax.yaxis.label
    text = label.get_text()
    if not text or '\n' in text:
        return
    allowance = region_h_in + 2.0 * layout.pad_top_in
    length = _y_title_extent_in(fig, ax)
    if length <= allowance:
        return
    words = text.split()
    if len(words) < 2:
        _log(f'    [ytitle] {text!r} is {length:.4f}in against {allowance:.4f}in allowed and is a single word, so it cannot be wrapped')
        return
    renderer = fig.canvas.get_renderer()
    font = label.get_fontproperties()
    cache = {}

    def width_in(s):
        if s not in cache:
            w, _, _ = renderer.get_text_width_height_descent(s, font, ismath=False)
            cache[s] = w / fig.dpi
        return cache[s]
    for lines in range(2, len(words) + 1):
        best, best_max = (None, None)
        for cuts in itertools.combinations(range(1, len(words)), lines - 1):
            bounds = (0,) + cuts + (len(words),)
            chunks = [' '.join(words[a:b]) for a, b in zip(bounds, bounds[1:])]
            widest = max((width_in(c) for c in chunks))
            if best_max is None or widest < best_max:
                best, best_max = (chunks, widest)
        if best_max <= allowance:
            candidate = '\n'.join(best)
            label.set_text(candidate)
            fig.canvas.draw()
            got = _y_title_extent_in(fig, ax)
            _log(f'    [ytitle] wrapped onto {lines} lines: {length:.4f}in exceeded the {allowance:.4f}in a {region_h_in:.3f}in region allows; now {got:.4f}in')
            _log(f'    [ytitle] {text!r} -> {candidate!r}')
            return
    label.set_text(text)
    fig.canvas.draw()
    _log(f'    [ytitle] {text!r} is {length:.4f}in and does not fit {allowance:.4f}in on any number of lines; left as-is for the clipping guard to report')

def apply(fig, ax, spec, profile):
    layout = profile.layout
    if layout is None:
        return None
    region_h_in = layout.region_h_in
    region_w_in = layout.region_w_in
    fig.canvas.draw()
    _wrap_y_title(fig, ax, layout, region_h_in)
    cap_in = _settings.constant('rowstack', 'CAP_RATIO') * profile.base_pt
    ascent_in = _settings.constant('rowstack', 'FONT_BOX_ASCENT_RATIO') * profile.base_pt
    descent_in = _settings.constant('rowstack', 'FONT_BOX_DESCENT_RATIO') * profile.base_pt
    leading_in = layout.leading_in
    legend_extra_in = leading_in / 2.0 if layout.legend_extra_in is None else layout.legend_extra_in
    rows, taken = _collect(fig, ax, spec)
    ticks = [t for t in ax.get_xticklabels() if t.get_text()]
    if not ticks:
        raise RuntimeError(f'{profile.name} lays out from the x tick row, but this figure has no x tick labels. This is a twoway_pgf layout defect, not something your script should work around: please report it on the issue tracker with this log and the spec you passed. A named format with layout: null falls back to constrained layout, but it opts this figure out of the shared plot region, so it will stop matching the rest of its set -- it is a documented escape hatch, not the fix for a failed render.')
    axes_bottom = ax.get_position().y0 * profile.height_in
    tick_baseline = _inches(ticks[0], fig).y1 - ascent_in
    tick_offset_pt = (axes_bottom - tick_baseline) * 72.0
    offsets_pt, cursor = ([], tick_offset_pt)
    for kind, _ in rows:
        cursor += leading_in * 72.0
        if kind == 'legend':
            cursor += legend_extra_in * 72.0
        offsets_pt.append(cursor)
    extra_legend_rows = 0
    if taken['legend'] is not None and taken['legend_side'] == 'bottom':
        handles, labels, ncols, _ = taken['legend']
        extra_legend_rows = max(0, -(-len(labels) // max(1, ncols)) - 1)
    below_in = (offsets_pt[-1] if offsets_pt else tick_offset_pt) / 72.0 + extra_legend_rows * leading_in + descent_in + layout.pad_top_in
    fig.set_layout_engine('none')
    created = []
    pad_left_eff = layout.pad_left_in

    def _lay(height_in, created):
        for artist in created:
            artist.remove()
        fig.set_size_inches(profile.width_in, height_in)
        ax.set_position([pad_left_eff / profile.width_in, below_in / height_in, region_w_in / profile.width_in, region_h_in / height_in])
        made = _place(fig, ax, rows, offsets_pt, taken, layout, profile, below_in, height_in, descent_in, leading_in, region_w_in, region_h_in, pad_left_eff)
        fig.canvas.draw()
        return made
    for _ in range(_HEIGHT_PASSES):
        height_in = layout.pad_top_in + region_h_in + below_in
        created = _lay(height_in, created)
        tight = fig.get_tightbbox(fig.canvas.get_renderer())
        shortfall = fig.bbox_inches.y0 + layout.pad_top_in - tight.y0
        if shortfall <= _HEIGHT_TOLERANCE_IN:
            break
        below_in += shortfall
    else:
        raise RuntimeError(f'the figure height did not settle in {_HEIGHT_PASSES} passes ({shortfall * 72:.2f}pt still below the box). This is a twoway_pgf layout defect, not something your script should work around: please report it on the issue tracker with this log and the spec you passed. A named format with layout: null falls back to constrained layout, but it opts this figure out of the shared plot region, so it will stop matching the rest of its set -- it is a documented escape hatch, not the fix for a failed render.')
    if layout.centre_narrow_ink and region_w_in < layout.slot_w_in - 1e-09:
        tight = fig.get_tightbbox(fig.canvas.get_renderer())
        target = layout.pad_left_in + layout.slot_w_in / 2.0
        shift_in = target - (tight.x0 + tight.x1) / 2.0
        pad_left_eff = layout.pad_left_in + shift_in
        created = _lay(height_in, created)
        moved = fig.get_tightbbox(fig.canvas.get_renderer())
        got = (moved.x0 + moved.x1) / 2.0
        _log(f"    [layout] narrowed region {region_w_in:.3f}in against the profile's {layout.region_w_in:.3f}in: content shifted {shift_in * 72:+.2f}pt so the INK centres on the slide (residual {(got - target) * 72:+.2f}pt)")
        if abs(got - target) > _HEIGHT_TOLERANCE_IN:
            raise RuntimeError(f'centring a narrowed panel left the ink {(got - target) * 72:.2f}pt off target, so the ink did not move rigidly with the axes. Something below the axes is positioned from the figure box rather than from the panel.')
    shape = ', '.join((f'{kind}@{i}' for i, (kind, _) in enumerate(rows, start=2)))
    _log(f"    [layout] fixed region{(' TALL' if spec.get('tall') else '')} {region_w_in:.3f} x {region_h_in:.3f}in; figure {profile.width_in:.3f} x {height_in:.3f}in; rows: tick@1" + (f', {shape}' if shape else ''))
    _log(f'    [layout] leading {leading_in:.4f}in baseline-to-baseline -> {leading_in - cap_in:.4f}in of whitespace at every junction' + (f'; {legend_extra_in:.4f}in extra before the legend' if taken['legend'] is not None else ''))
    return profile.with_height(height_in)

def _collect(fig, ax, spec):
    edges = []
    for artist in list(ax.texts):
        align = getattr(artist, '_twpgf_edge_align', None)
        if align is not None:
            edges.append((artist.get_text(), align))
            artist.remove()
    xtitle = spec['xtitle'] if spec['xtitle'] else ''
    ax.set_xlabel('')
    legend = fig.legends[0] if fig.legends else None
    legend_data = None
    if legend is not None:
        legend_data = (list(legend.legend_handles), [t.get_text() for t in legend.get_texts()], getattr(legend, '_ncols', 1), legend.get_texts()[0].get_fontsize())
        legend.remove()
    side = 'bottom'
    wanted = (spec.get('legend') or {}).get('position')
    if wanted in ('right', 'separate'):
        side = wanted
    rows = []
    if edges:
        rows.append(('edges', edges))
    if xtitle:
        rows.append(('title', xtitle))
    if legend_data is not None and side == 'bottom':
        rows.append(('legend', legend_data))
    if legend_data is not None and side == 'separate':
        fig._twpgf_separate_legend = legend_data
    return (rows, {'legend': legend_data, 'legend_side': side})

def _clamp(fig, artist, width_in, offset_pt):
    box = _inches(artist, fig)
    shift = 0.0
    if box.x1 > width_in:
        shift = width_in - box.x1
    if box.x0 + shift < 0.0:
        shift = -box.x0
    if abs(shift) < 1e-09:
        return 0.0
    artist.set_position((shift * 72.0, offset_pt))
    return shift

def _place(fig, ax, rows, offsets_pt, taken, layout, profile, below_in, height_in, descent_in, leading_in, region_w_in, region_h_in, pad_left_in):
    created = []
    for index, (kind, payload) in enumerate(rows):
        offset = -offsets_pt[index]
        if kind == 'edges':
            for text, align in payload:
                created.append(ax.annotate(text, xy=(0.0 if align == 'left' else 1.0, 0.0), xycoords='axes fraction', xytext=(0, offset), textcoords='offset points', ha=align, va='baseline', annotation_clip=False))
        elif kind == 'title':
            title = ax.annotate(payload, xy=(0.5, 0.0), xycoords='axes fraction', xytext=(0, offset), textcoords='offset points', ha='center', va='baseline', annotation_clip=False)
            created.append(title)
            fig.canvas.draw()
            moved = _clamp(fig, title, profile.width_in, offset)
            if moved:
                _log(f"    [layout] x title is wider than the box allows centred on the plot region; shifted {abs(moved) * 72:.2f}pt {('left' if moved < 0 else 'right')} to fit.")
    if taken['legend'] is None:
        return created
    handles, labels, ncols, fontsize = taken['legend']
    if taken['legend_side'] == 'separate':
        return created
    if taken['legend_side'] == 'right':
        gap_in = leading_in / 2.0
        legend = fig.legend(handles, labels, loc='center left', bbox_to_anchor=((pad_left_in + region_w_in + gap_in) / profile.width_in, 1.0 - (layout.pad_top_in + region_h_in / 2.0) / height_in), bbox_transform=fig.transFigure, ncols=1, frameon=False, fontsize=fontsize, borderpad=0.0, borderaxespad=0.0, labelspacing=max(0.0, leading_in * 72.0 / fontsize - 1.0), handletextpad=_settings.value('legend')['handletextpad'])
        fig.canvas.draw()
        box = _inches(legend, fig)
        _log(f'    [layout] legend to the RIGHT of the region: {box.width:.3f}in wide, in the {profile.width_in - pad_left_in - region_w_in:.3f}in reserved beyond the region; costs no row below the axes')
        if box.x1 > profile.width_in + 1e-06:
            _log(f'    [layout] WARNING legend runs {(box.x1 - profile.width_in) * 72:.2f}pt past the figure box; widen the profile or narrow the region')
        created.append(legend)
        return created
    target_baseline = below_in - offsets_pt[-1] / 72.0
    target_y0 = target_baseline - descent_in
    labelspacing = leading_in * 72.0 / fontsize - 1.0
    anchor_y = 1.0
    legend = None
    for _ in range(_LEGEND_SOLVE_PASSES):
        if legend is not None:
            legend.remove()
        legend = fig.legend(handles, labels, loc='upper center', bbox_to_anchor=((pad_left_in + region_w_in / 2.0) / profile.width_in, anchor_y), bbox_transform=fig.transFigure, ncols=ncols, frameon=False, fontsize=fontsize, borderpad=0.0, borderaxespad=0.0, labelspacing=max(0.0, labelspacing), handletextpad=_settings.value('legend')['handletextpad'])
        fig.canvas.draw()
        texts = legend.get_texts()
        ys = sorted((_inches(t, fig).y0 for t in texts), reverse=True)
        row_tops = []
        for value in ys:
            if not row_tops or (row_tops[-1] - value) > _ROW_CLUSTER_IN:
                row_tops.append(value)
        first = row_tops[0]
        pitch_error = 0.0
        if len(row_tops) > 1:
            pitch_error = first - row_tops[1] - leading_in
            if abs(pitch_error) > _LEGEND_TOLERANCE_IN:
                labelspacing -= pitch_error * 72.0 / fontsize
        offset_error = first - target_y0
        if abs(offset_error) > _LEGEND_TOLERANCE_IN:
            anchor_y -= offset_error / height_in
        if abs(pitch_error) <= _LEGEND_TOLERANCE_IN and abs(offset_error) <= _LEGEND_TOLERANCE_IN:
            break
    else:
        raise RuntimeError(f'the legend row pitch did not settle in {_LEGEND_SOLVE_PASSES} passes (pitch off by {pitch_error * 72:.2f}pt, offset by {offset_error * 72:.2f}pt). This is a twoway_pgf layout defect, not something your script should work around: please report it on the issue tracker with this log and the spec you passed. A named format with layout: null falls back to constrained layout, but it opts this figure out of the shared plot region, so it will stop matching the rest of its set -- it is a documented escape hatch, not the fix for a failed render.')
    created.append(legend)
    box = _inches(legend, fig)
    shift = 0.0
    if box.x1 > profile.width_in:
        shift = profile.width_in - box.x1
    if box.x0 + shift < 0.0:
        shift = -box.x0
    if abs(shift) > 1e-09:
        legend.set_bbox_to_anchor(((pad_left_in + region_w_in / 2.0 + shift) / profile.width_in, anchor_y), transform=fig.transFigure)
        _log(f"    [layout] legend is wider than the box allows centred on the plot region; shifted {abs(shift) * 72:.2f}pt {('left' if shift < 0 else 'right')} to fit.")
    return created
