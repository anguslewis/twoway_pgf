*! Select the Python interpreter.
program define _twoway_pgf_select, rclass
    version 16
    _twoway_pgf_root
    local registry `"`r(registry)'"'
    local texbin ""
    capture confirm file "`registry'"
    if !_rc {
        tempname f
        file open `f' using "`registry'", read text
        file read `f' registered
        file read `f' chosen
        file read `f' texbin
        file close `f'
        if "`registered'" != "0.1.1" {
            di as error "twoway_pgf wrapper 0.1.1; registered backend `registered'."
            di as error "Install the matching backend: twoway_pgf_setup"
            exit 499
        }
        quietly python query
        if r(initialized) {
            findfile _twoway_pgf_same.py
            local same "`r(fn)'"
            capture noisily python script "`same'", args("`chosen'")
            if _rc exit 499
        }
        else python set exec "`chosen'"
    }
    findfile twoway_pgf_bridge.py
    local bridge "`r(fn)'"
    // Version preflight precedes spec parsing, CSV export, or any Matplotlib import.
    python script "`bridge'", args("--check" "0.1.1")
    return local texbin `"`texbin'"'
end
