*! Resolve package storage before initializing Python.
program define _twoway_pgf_root, rclass
    version 16
    local root "`c(sysdir_plus)'twoway_pgf"
    local registry "`root'/current.txt"
    return local path `"`root'"'
    return local registry `"`registry'"'
end
