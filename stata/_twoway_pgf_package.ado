*! Locate clone assets or unpack the net-install payload.
program define _twoway_pgf_package, rclass
    version 16
    _twoway_pgf_root
    local root `"`r(path)'"'
    findfile twoway_pgf_setup.ado
    local directory = substr(`"`r(fn)'"', 1, strlen(`"`r(fn)'"') - strlen("twoway_pgf_setup.ado"))
    capture confirm file "`directory'../bootstrap/setup.sh"
    if !_rc {
        return local path `"`directory'../"'
        exit
    }
    findfile twoway_pgf_stata-0.1.1.zip
    local bundle `"`r(fn)'"'
    local payload_id "0.1.1-cf57af02cc9a"
    local package "`root'/package-`payload_id'"
    capture confirm file "`package'/.payload-ready"
    if _rc {
        mata: st_local("qpackage", "'" + subinstr(st_local("package"), "'", "'" + char(34) + "'" + char(34) + "'") + "'")
        shell /bin/mkdir -p `qpackage'
        local previous `"`c(pwd)'"'
        capture quietly cd "`package'"
        if _rc {
            di as error "twoway_pgf: cannot create/access payload directory `package'. Check write permissions for Stata's PLUS directory."
            exit 603
        }
        capture noisily unzipfile "`bundle'", replace
        local status = _rc
        quietly cd `"`previous'"'
        if `status' exit `status'
        confirm file "`package'/bootstrap/setup.sh"
        confirm file "`package'/artifacts/twoway_pgf-0.1.1-py3-none-any.whl"
        tempname ready
        file open `ready' using "`package'/.payload-ready", write text
        file write `ready' "`payload_id'" _n
        file close `ready'
    }
    return local path `"`package'/"'
end
