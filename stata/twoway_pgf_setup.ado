*! twoway_pgf_setup 0.1.0 -- validate existing Python; installation is opt-in
program define twoway_pgf_setup, rclass
    version 16
    syntax [, PYthon(string) ENVPath(string) MANager(string) TEXBin(string) OFFLine INSTALL]
    if c(os) == "Windows" {
        di as error "Setup uses a POSIX shell on macOS/Linux. Configure Python manually on Windows."
        exit 198
    }
    _twoway_pgf_root
    local root `"`r(path)'"'
    local registry `"`r(registry)'"'
    local mode "validate"
    if "`install'" != "" local mode "install"
    if `"`python'"' != "" & "`mode'" != "validate" {
        di as error "python() selects an existing environment; omit install."
        exit 198
    }
    if `"`manager'"' != "" & "`mode'" != "install" {
        di as error "manager() requires install; supply the path to your installed conda executable."
        exit 198
    }
    if `"`envpath'"' != "" & "`mode'" != "install" {
        di as error "envpath() selects where to create a Conda environment and requires install; use python() to select an existing environment."
        exit 198
    }
    // Recheck this package's saved interpreter before Stata's auto-detected Python.
    if "`mode'" == "validate" & `"`python'"' == "" {
        capture confirm file "`registry'"
        if !_rc {
            tempname previous
            file open `previous' using "`registry'", read text
            file read `previous' registered
            file read `previous' python
            file read `previous' recorded_texbin
            file close `previous'
            if `"`texbin'"' == "" local texbin `"`recorded_texbin'"'
        }
        if `"`python'"' == "" {
            capture quietly python query
            if !_rc local python `"`r(execpath)'"'
        }
    }
    _twoway_pgf_package
    local package `"`r(path)'"'
    local script "`package'bootstrap/setup.sh"
    confirm file "`script'"
    tempfile request receipt
    tempname f
    file open `f' using "`request'", write text
    file write `f' `"`python'"' _n `"`root'"' _n `"`manager'"' _n `"`texbin'"' _n
    file write `f' "`=cond("`offline'" == "", "0", "1")'" _n
    file write `f' "`mode'" _n
    file write `f' `"`envpath'"' _n
    file close `f'
    // POSIX single-quote escaping.
    foreach arg in script request receipt {
        mata: st_local("q`arg'", "'" + subinstr(st_local("`arg'"), "'", "'" + char(34) + "'" + char(34) + "'") + "'")
    }
    shell /bin/bash `qscript' `qrequest' `qreceipt'
    capture confirm file "`receipt'"
    if _rc {
        di as error "twoway_pgf setup failed; see diagnostic above. Previous registration is unchanged."
        if "`mode'" == "validate" {
            di as error "No Python or packages were installed. Supply python(" char(34) "/path/to/python" char(34) ") for a compatible environment."
            di as error "To create the package environment with your existing Conda installation, run twoway_pgf_setup, install."
        }
        exit 499
    }
    file open `f' using "`receipt'", read text
    file read `f' backend
    file read `f' chosen
    file read `f' chosen_texbin
    file close `f'
    if "`backend'" != "0.1.0" {
        di as error "Setup receipt version `backend' does not match wrapper 0.1.0."
        exit 499
    }
    quietly python query
    if r(initialized) {
        capture noisily python script "`package'stata/_twoway_pgf_same.py", args("`chosen'")
        if _rc exit 499
    }
    else python set exec "`chosen'"
    // Registration is atomic and happens only after diagnostics and selection succeed.
    python script "`package'bootstrap/register.py", args("`receipt'" "`registry'")
    return local python_exec `"`chosen'"'
    return local texbin `"`chosen_texbin'"'
    return local registry `"`registry'"'
    di as result "twoway_pgf 0.1.0 setup passed; Python: `chosen'"
end
