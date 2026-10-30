{smcl}
{title:twoway_pgf 0.1.1 — LaTeX-native figures}

{p 4 4 2}
Export line, scatter, bar, waterfall and hexbin figures as PGF, with optional
PDF previews and JSON provenance manifests. Requires Stata 16+, external Python
3.12.14, NumPy 2.2.6, pandas 2.3.3, Matplotlib 3.10.9 and working TeX.

{title:Setup}
{p 4 4 2}Conda and TeX must already be installed. The package never installs an environment manager or TeX.
{p 4 4 2}{cmd:twoway_pgf_setup, install} creates/reuses the pinned package environment through your existing Conda installation, checks TeX and records the interpreter path. Other existing environments are not modified.
{p 4 4 2}{cmd:twoway_pgf_setup} rechecks existing Python and TeX and records the working paths; no software installation.
{p 4 4 2}{cmd:twoway_pgf_setup, python("/your/env/bin/python")} validates that environment.
{p 4 4 2}For manual creation, use the supplied {cmd:environment.yml}, activate {cmd:twoway_pgf}, install the bundled wheel and pass its Python executable to setup.
{p 4 4 2}Optional {cmd:texbin("/Library/TeX/texbin")}, {cmd:offline}; {cmd:manager("/path/to/conda")} and {cmd:envpath("/path/to/new/environment")} require {cmd:install}. Conda is found through {cmd:CONDA_EXE} or PATH; already installed compatible mamba managers work too. There is no permanent-setting option.
{p 4 4 2}Installation normally creates a named {cmd:twoway_pgf} environment in Conda's configured default location. {cmd:envpath()} chooses an exact environment directory instead. Payload, package state and the {cmd:current.txt} interpreter record stay in {cmd:PLUS/twoway_pgf}. Later sessions read that record automatically, including for an environment created with {cmd:envpath()}. Existing environments are never moved or overwritten. Finder/Dock users may need explicit {cmd:manager()} and {cmd:texbin()} paths because terminal PATH settings are not inherited.

{p 4 4 2}The command serializes current data and calls the same Python renderer.
Add {cmd:settings("/project/utilities/visual_settings.json")} to choose an editable theme.
Full options, installation instructions, settings and limitations:
{browse "https://github.com/anguslewis/twoway_pgf#readme":README}.

{p 4 4 2}Tested and run on macOS (StataNow 19.5) and Linux/Sherlock (Stata 17),
including standalone installation, fresh-session interpreter reuse and Python rendering.
Automatic environment creation supports Apple-silicon macOS and Linux x86-64.
Other POSIX systems can select a manually created environment with {cmd:python()}.
Windows needs manual configuration and remains untested. Stata 16 is the minimum target.
