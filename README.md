# twoway_pgf

Publication-quality, LaTeX-native figures from Python and Stata.

Why use `twoway_pgf`?

1. **Figures that fit your LaTeX document.** Export PGF figures with text and
   mathematics typeset by TeX, at the exact font sizes and dimensions you specify.
2. **Consistency across Python and Stata.** Produce identical graphs from the
   same data, plot options and visual settings in either language. Switching
   between Python and Stata does not change how your figures look.
3. **Minimize case-by-case figure settings.** Fonts, colors, plot dimensions,
   line patterns, and other visual choices are stored in one project-specific
   settings file. These settings are highly flexible. For example the set of
   line colors and patterns used can vary across the number of series plotted.
   Paper and slide versions are produced from single function calls. Named
   formats supply the dimensions, fonts, and layout for each use case, without
   manually producing multiple figures.
4. **AI tools can see plots natively in LaTeX.** PGF vector figures expose
   plotted paths, coordinates, and labels as readable TeX. AI tools reviewing a
   manuscript can inspect these alongside the text, helping them reason about
   the plots without relying only on PDF or PNG previews. PGF stores drawing
   coordinates; it does not guarantee recovery of the original data.

The package has a Python backend built on Matplotlib’s PGF backend, and a Stata
wrapper that calls it through Stata’s built-in Python integration. Whether you
plot from Python or Stata, the same Python code draws the figure. TeX supplies
font measurements and can also compile a PDF preview.

An editable `visual_settings.json` stores your visual preferences. It is
analogous to a Stata scheme, but also defines named paper and slide formats and
rules for choosing styles: for example, which colors and line patterns to use
as the number of series changes, and how to highlight an emphasis series. Keep
the file with your project and pass its path when plotting from either language.

The aim is to specify your data and the meaning of a graph in each call, while
the JSON file handles its appearance. Set your project’s preferences once,
then produce consistent figures with minimal case-by-case editing.

Developed for Lewis and Xie (2026),
*Firm-Level Gains from Financial Integration*.

## Installation

**Conda and TeX must already be installed.** The package never installs an
environment manager or TeX.

### Stata

```stata
net install twoway_pgf, from("https://raw.githubusercontent.com/anguslewis/twoway_pgf/v0.1.0")
twoway_pgf_setup, install
```

### Python

```sh
git clone --branch v0.1.0 https://github.com/anguslewis/twoway_pgf.git
cd twoway_pgf
conda env create --file environment.yml
conda activate twoway_pgf
python -m pip install --no-index --no-deps artifacts/twoway_pgf-0.1.0-py3-none-any.whl
```

See [Technical details of installation](#technical-details-of-installation) for
existing-environment setup, configuration and other platforms.

## Graph types and common inputs

Choose [line](#line-plots), [scatter](#scatter-plots),
[bar](#bar-charts) (ungrouped, grouped or stacked), [waterfall](#waterfall-charts)
or [hexbin](#hexbin-plots). Every call needs the following:

| Required input | Stata | Python |
|---|---|---|
| Graph type | First argument | `type` |
| Data | Current data in memory | `data` (CSV path) |
| Output name | `name()` | `name` |
| Output directory | `outdir()` | `outdir` |
| Vertical-axis title | `ytitle()` | `ytitle` |
| Columns to plot | Positional variables and chart options | Chart-specific fields below |

Use a safe filename stem beginning with a letter for `name`. Stata preserves
your current data while exporting a temporary CSV. Python reads the CSV you
specify. Relative paths are resolved against the current working directory.

### Reading the options

Both languages use the same renderer and plot specification, but **their option
names and structures are not identical**. Simple names such as `name`, `outdir`,
`ytitle`, `xtitle` and `formats` match. Stata uses space-separated option values;
Python uses dictionary entries and lists.

The chart sections explain each choice once, using Python/JSON field names and
showing Stata equivalents where needed. `series[].label` means the `label`
field of each object in the `series` list; it is not a literal dictionary key.

**Full-spec options** are available directly in Python or through a saved JSON
specification in either language. Some have no Stata convenience option.
Use `python -m twoway_pgf render SPEC_FILE` or Stata `twoway_pgf using SPEC_FILE`.

That JSON file contains the same plot dictionary passed to Python `render()`.
It describes one graph; the separate visual-settings JSON describes your theme.

### Shared optional controls

Most calls can inherit appearance from the [project settings](#project-settings).
Use these controls when the graph needs an override:

| Choice | Stata | Python |
|---|---|---|
| Horizontal-axis title | `xtitle()` | `xtitle` |
| Output formats | `formats()` | `formats` (list of format names) |
| Axis limits | `xrange()`, `yrange()` | `xlim`, `ylim` (lower/upper bounds) |
| Tick positions and labels | `xlabel()`, `ylabel()` | `xticks`, `yticks`, plus `xtick_labels`, `ytick_labels` |
| Line/scatter series labels | `labels(...)` | `series[].label` |
| Line/scatter colors and opacity | `colors(...)`, `alphas(...)` | `series[].color`, `series[].alpha` |
| Hide the legend | `nolegend` | `legend.show: false` |
| Legend columns | `legendcols()` | `legend.cols` |

Python/JSON fields above use JSON notation; in Python code write `False`,
`True` and `None` for JSON's `false`, `true` and `null`. Multiword Stata series
labels need compound quotes: `` labels(`""Set A" "Set B""') ``.

## Project settings

Keep a copy of `visual_settings.json` with your project, for example under
`utilities`. To start from the bundled settings:

```sh
mkdir -p utilities
python -m twoway_pgf copy-settings utilities/visual_settings.json
```

Pass the file to each graph with Stata `settings("utilities/visual_settings.json")`
or Python `render(spec, settings="utilities/visual_settings.json")`. In Python,
`settings` is a function argument, not a field inside the plot dictionary.

- **`base`:** your palette, line patterns, markers, strokes, grid, legend rules
  and other visual defaults. Chart defaults also live here under `spec_defaults`.
- **`formats`:** named bundles of dimensions, fonts and layout, with optional
  visual overrides. The bundled defaults produce both `paper` and `slides`.
- **`default_formats`:** which named formats to produce when a call omits `formats`.

The default line rules choose colors and patterns automatically, switch to
grayscale above five series, and give an emphasis series its own style. All
chart types share the same series blue, `#0067A0`; the seven-color palette
derives from Wong (2011). The aim is to set these preferences once and keep
individual calls focused on data, labels and meaning.

The settings file is selected by explicit path, then `TWOWAY_PGF_SETTINGS`, then
the bundled default. Each call reloads one complete file; it does not search the
current directory. Within that file, resolution is base, chart defaults, format
visual overrides, then explicit plot options. See the technical details for
[format dimensions and customization](#technical-details).

## Plot types

Supply the common required inputs above for each graph type below. Optional visual
overrides can usually stay in your JSON settings.

### Line plots

**Stata data arguments:** `line yvars xvar, ...`

**Python data fields:** `x`, `series[].y`.

- **Required:** an `x` column and a `series` list naming each `y` column.
  Stata takes the y variables first, followed by x.
- **Optional labels, colors and opacity:** use the shared controls above.
- **Optional line patterns:** `series[].pattern`; Stata `patterns(...)`.
- **Optional emphasis:** `emphasis` names an existing y series to highlight;
  Stata `emphasis()`.
- **Full-spec options:** confidence `bands` with `lo`/`hi` columns; `step` with
  declared series `jumps`; per-series `linewidth`, `marker` and `reduce`.

### Scatter plots

**Stata data arguments:** `scatter yvars xvar, ...`

**Python data fields:** `x`, `series[].y`.

- **Required:** an `x` column and a `series` list naming each `y` column.
  Stata takes the y variables first, followed by x.
- **Optional labels, colors and opacity:** use the shared controls above.
- **Optional symbols and sizes:** `series[].symbol` and `series[].size`;
  Stata `symbols(...)` and `msizes(...)`.
- **Optional rasterization:** `rasterize` is true, false or null (automatic);
  Stata `rasterize(on)`, `rasterize(off)` or `rasterize(auto)`.
  `raster_dpi` corresponds to Stata `rasterdpi()`.
- **Full-spec options:** a separate `x` column per series and marker `edge_width`.

### Bar charts

**Stata data arguments:** `bar valuevar, category(categoryvar) ...`

**Python data fields:** `value`, `category`.

- **Required:** `value` and `category` columns. Supply one prepared value per
  category/group/segment combination; the renderer does not aggregate observations.
- **Optional groups:** `group` puts bars side by side; Stata `group()`.
- **Optional stacks:** `series` identifies stacked segments; Stata `series()`.
  Here `series` is a column name, rather than the list used for line/scatter plots.
- **Optional label columns:** `category_label`, `group_label`, `series_label`;
  Stata `catlabel()`, `grplabel()`, `serlabel()`.
- **Optional uncertainty:** `se`, or both `lower` and `upper`, name columns;
  Stata uses the same names. `se_on` chooses `total` or `segment`; Stata `seon()`.
- **Optional appearance overrides:** `colors` and `baseline` use the same names;
  `bar_width` and `group_gap` correspond to Stata `barwidth()` and `groupgap()`.

### Waterfall charts

**Stata data arguments:** `waterfall valuevars, ...`

**Python data fields:** `bars[].value_col`, `bars[].label`.

- **Required:** a `bars` list with a `value_col` and `label` for each bar.
  Stata takes value columns positionally and labels through `labels(...)`;
  omitted Stata labels default to column names.
- **Optional bar kinds:** each bar's `kind` is `delta` (the default) or `total`;
  Stata `kinds()`. A total must equal the sum of the deltas.
- **Optional uncertainty:** each bar's `sd_col`; Stata `sdvars(...)`.
- **Optional row selection:** `row_filter` selects exactly one data row;
  Stata `where(column value ...)`. Omit it if the CSV already has one row.
- **Full-spec appearance overrides:** `up_color`, `down_color`, `total_color`,
  `bar_width` and `connectors`. Their defaults are in the settings JSON.

### Hexbin plots

**Stata data arguments:** `hexbin yvar xvar, bins(#) ...`

**Python data fields:** `x`, `y`, `bins` (or `value` for pre-binned cells).

- **Required for raw observations:** `x` and `y` columns, plus a positive integer
  `bins` for binning resolution. Stata takes y first, then x, with `bins()`.
- **Required color choice:** ordered count cut points in `cuts`, or a log color
  scale. Stata uses `cuts(...)` or `cscale(log)`.
- **Optional color scale:** `color_scale`; Stata `cscale()`. `ramp` uses the same
  name in both languages.
- **Optional size scale:** `srange` uses the same name; `size_scale` corresponds
  to Stata `sizescale()`. Disable proportional sizing with `sizeprop: false`
  or Stata `nosizeprop`.
- **Optional key:** `key_mode`, `key_steps`, `key_ticks`, `key_title`;
  Stata `keymode()`, `keysteps()`, `keyticks()`, `keytitle()`.
- **Full-spec options:** pre-binned cells with a count column named by `value`
  instead of `bins`, and explicit cell dimensions through `hex_half_width`
  and `hex_half_height`.

The external log-count key can overflow the fixed `paper`/`slides` canvases.
Use `nolegend` / `legend.show: false`, or a suitable
constrained-layout format such as `paper_short`.

## Technical details

### Technical details of installation

- **Requirements:** [environment.yml](environment.yml) pins Python 3.12.14,
  NumPy 2.2.6, pandas 2.3.3 and Matplotlib 3.10.9, plus install/build tools.
  TeX needs PGF and Latin Modern; it measures fonts for PGF and compiles PDFs.
- **Managed installation:** `twoway_pgf_setup, install` uses the platform's shipped
  lock and bundled wheel to create/reuse the named environment `twoway_pgf`
  in Conda's configured default environment location,
  validates packages and TeX, and records its Python path. Other environments
  are not modified. Miniconda, Miniforge, Anaconda or an already installed
  compatible mamba manager can provide Conda-compatible environment management.
- **Existing environment:** `twoway_pgf_setup, python("/your/env/bin/python")`
  validates and records that interpreter. Later, plain `twoway_pgf_setup`
  rechecks the saved registration first, then Stata's Python and active Conda/PATH.
  These routes install no software; the package and pinned dependencies must
  already be present. A failed check leaves the previous registration unchanged.
  If TeX validation fails after `install` creates the environment, correct
  `texbin()` and repeat `install`; setup retains and rechecks that environment.
  If you remove that environment, `install` recreates it after checking the
  destination is free. Conda retains your normal umask for environment/cache permissions.
- **Finding Conda and TeX:** setup checks `CONDA_EXE` or PATH for Conda.
  `manager("/absolute/path/to/conda")` selects it explicitly with `install`.
  Finder/Dock-launched Stata may not inherit your terminal's PATH. In that case,
  supply `manager()` and `texbin()` explicitly; `conda info --base` in your
  normal terminal gives the directory containing `bin/conda`.
  Use `texbin("/Library/TeX/texbin")`, or your TeX executable directory, if TeX
  is absent from PATH. Missing packages/fonts are reported during validation.
- **Downloads and destination:** `install` downloads environment dependencies
  when needed; Conda uses its configured environment directories and package cache.
  `offline` requires cached packages. `envpath("/absolute/path/to/new/environment")`
  creates the environment at that exact path instead of creating a named environment.
  Payload, package state and the interpreter record stay in `PLUS/twoway_pgf`,
  visible through Stata's `sysdir`. Existing environments are never moved or overwritten;
  select a prepared environment with `python()`.
- **Saved paths:** `PLUS/twoway_pgf/current.txt` records the package version,
  Python executable and TeX-bin path. Subsequent graphs read it after a restart.
  Setup selects Python for the current session and does not change Stata's
  permanently saved Python preference. Run setup before Python initializes;
  restart Stata to switch an initialized interpreter. Rechecking the same one is allowed.
  The record points to the environment wherever Conda created it, including an
  explicit `envpath()`. Later sessions use the same record without repeating that option.
- **Manual Python installation:** the YAML pins the runtime and build tools;
  Conda resolves supporting packages. For the exact tested macOS ARM64 stack,
  use `conda create -n twoway_pgf --file locks/osx-arm64.txt`. To install from
  source, use `python -m pip install --no-deps --no-build-isolation .` in that
  environment. Direct Python use needs no Stata setup or registry. Obtain its
  executable with `python -c "import sys; print(sys.executable)"` to select it in Stata.
- **Linux and clusters:** the same Stata installation commands apply on Linux.
  Make the site's Stata/TeX modules and existing Conda available first. On a
  shared cluster, `envpath("/project/storage/twoway_pgf")` can place the environment
  on suitable shared storage. Keep Stata's PLUS directory consistent across jobs
  so they find the interpreter record.
- **Architectures:** automatic environment creation supports Apple-silicon Macs
  (`osx-arm64`) and Linux x86-64 (`linux-64`). Use the matching file in `locks`
  for exact manual creation. On other POSIX systems, including Intel Macs,
  create the YAML environment manually and validate it with `python()`.
  Windows needs manual Stata `python set exec` configuration and remains untested.
  Wrapper and backend must both be version 0.1.0.

### Outputs and LaTeX

- **Figures:** `<name>_<format>.pgf` and, by default, `<name>_<format>_preview.pdf`.
  Full-spec `preview: false` skips PDFs. `render()` returns output paths per format.
- **Raster layers:** `<name>_<format>-img*.png` files accompany rasterized PGF
  content. Keep them with the PGF; they are different from full-figure PNG previews.
- **Separate legends:** output names use a `_leg` format suffix.
- **LaTeX:** load `pgf` and use `\input{<figure>.pgf}` at natural size;
  resizing also rescales fonts and strokes. For raster layers, define
  `\def\twpgfimagedir{figures/}` before the input.

### Labels and inputs

- Labels use TeX. Full-spec `escape_labels: true` or `twoway_pgf.texesc.escape()`
  handles literal text. In Stata use `\( ... \)` for math; dollar signs expand
  macros. Date axes use numeric positions and explicit tick labels in both languages.
- CSV/spec/settings files are trusted local inputs: TeX labels and preambles
  execute through your TeX installation. PyStata users call the same ado through
  their existing Stata session.

### Additional shared options and the full specification

| Choice | Stata | Python |
|---|---|---|
| Vertical reference lines | `xline()` | `reference_lines` entries with `axis: "x"` and `at` |
| Left/right horizontal titles | `xtitleleft()`, `xtitleright()` | `xtitle_left`, `xtitle_right` |
| Legend order and font size | `legendorder()`, `legendsize()` | `legend.order`, `legend.fontsize` |
| Separate legend | `separateleg` | `legend.position: "separate"` |
| Disable line reduction | `noreduce` | `reduce: false` |
| Manifest directory | `manifestdir()` | `render()` argument `manifest_dir` |
| Render timeout (default 600 s) | `timeout()` | `twoway_pgf.bridge.run_spec()` argument `timeout` |

The full spec also exposes `grid`, `log_x`, `log_y`, tick formatting/rotation,
horizontal reference lines, preview selection and literal-label escaping.
Accepted keys are defined in [spec.py](src/twoway_pgf/spec.py), with additional
editable defaults in [visual_settings.json](src/twoway_pgf/visual_settings.json).
Unknown keys are errors. Direct Python `render()` does not impose a timeout;
the bridge and command-line/Stata frontends do.

### Named format dimensions, inheritance and custom fonts

| Format | Canvas width (in) | Plot region (in) | Font |
|---|---:|---|---|
| paper | 5.525 | 4.525 × 2.25 | 10pt serif |
| paper_tall | 5.525 | 4.525 × 2.75 | 10pt serif |
| slides | 4.6094488 | 3.6094488 × 1.6407 | 8pt sans |
| slides_tall | 4.6094488 | 3.6094488 × 1.785988 | 8pt sans |
| paper2x1 | 3.185 | 2.15 × 2.15 | 10pt serif |
| slides2x1 | 2.70078739 | 1.823 × 1.36725 | 8pt sans |
| paper_short | 6.5 | Constrained layout; 3.4in canvas height | 10pt serif |

Fixed layout derives final canvas height from region, labels and measured ink.
`layout: null` selects constrained layout. Sizing, including tall variants,
belongs to named formats; there is no separate `tall` option.

Define a named format by adding a member to the settings file's `formats` collection.

`extends` merges objects recursively and replaces arrays. Missing parents,
cycles, duplicate keys, unknown settings, non-finite values, invalid dimensions,
colors and style references are errors.

Custom fonts/preambles with fixed layout need calibrated row-stack metrics and
matching `metrics_font_family`/`metrics_tex_preamble` declarations; otherwise use
constrained layout. The package cannot verify external calibration measurements.
Custom fonts/preambles may need additional TeX packages installed by the user.

### Validation, provenance and runtime behavior

- Dimension, clipped-ink, unexpected-rasterization, sidecar and reduction checks
  can reject a figure. Line/scatter missing observations are omitted as documented
  by the primitives. Waterfall values/SDs must be finite; SDs must be nonnegative.
- Hexbin cell counts must be at least 1. Start discrete cuts above 1 to avoid an
  empty first legend class. Constant unit-count log color is rejected; use cuts.
  Hexbin needs at least two distinct occupied cell centres along each axis,
  even with explicit dimensions; use scatter for identical-coordinate observations.
- Legend positions are `bottom`, `right`, `separate` and `none`; automatic `best`
  placement is unsupported. Separate legends require fixed layout; constrained
  formats such as `paper_short` can use a bottom legend.
- Reduced lines need two finite axis bounds or omitted bounds. For a one-sided
  limit, supply both bounds or disable reduction. This matters when a series
  exceeds its reduction cap. Scatter does not thin observations.
- Manifests record hashes, normalized spec, resolved settings, dimensions and
  dependency/TeX versions. Python defaults to `data.parent/manifests`; Stata's
  temporary-data form uses `outdir/manifests`. Override with the arguments above.
- Bundles are validated in staging. Superseded files are archived under `.archive`
  in the output directory; the manifest is published last. Concurrent writes to
  one output stem are unsupported. Publication is per figure, not atomic across
  all selected formats.
- In-process `render()` restores Matplotlib rc settings and serializes calls.
  The bridge and command-line/Stata frontends use a child process with a timeout
  and matching completion receipt. Debug tracing uses the `twoway_pgf` logger.

## Tested platforms and versions

**Tested and run on macOS and Linux**, including standalone Stata installation,
reuse of the saved interpreter in a fresh Stata session, and Python rendering.

- **macOS:** 26.5.2 (Apple silicon), StataNow **19.5**, TeX Live **2026**.
- **Linux:** x86-64 (Sherlock), Stata **17**, TeX Live **2019**.

Both use Python **3.12.14**, NumPy **2.2.6**, pandas **2.3.3** and
Matplotlib **3.10.9**. Stata **16+** is the target; version 16, Windows and
Intel Macs have not been tested.

## References

- Lewis, A. and O. Xie (2026). *Firm-Level Gains from Financial Integration.*
  Working paper.
- Hunter, J. D. (2007). "Matplotlib: A 2D Graphics Environment."
  *Computing in Science & Engineering*, 9(3), 90–95.
  [DOI](https://doi.org/10.1109/MCSE.2007.55).
- Matplotlib: [PGF backend documentation](https://matplotlib.org/stable/users/explain/text/pgf.html).
- Jann, B. (2019). [hexplot/heatplot](https://github.com/benjann/heatplot).
  The ported hexbin code retains its original MIT notice.
- Wong, B. (2011). "Color blindness." *Nature Methods*, 8, 441.
  [DOI](https://doi.org/10.1038/nmeth.1618).

## License

MIT © 2026 Angus Lewis. See [LICENSE](LICENSE).
The full Ben Jann 2019 MIT notice and dependency/palette attribution are
preserved in [NOTICES](NOTICES) and the hexbin source. Matplotlib, NumPy,
pandas, Python and TeX retain their respective licenses.
