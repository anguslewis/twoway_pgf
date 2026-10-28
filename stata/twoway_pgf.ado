*! twoway_pgf 0.1.0 -- CSV/spec serializer; setup is always explicit.
program define twoway_pgf
    version 16
    _twoway_pgf_select
    local texbin `"`r(texbin)'"'
    gettoken charttype 0 : 0
    if "`charttype'" == "using" {
        syntax anything(name=specpath) [, SETTINGS(string) TIMEOUT(real 600) MANIFESTdir(string)]
        local specpath : subinstr local specpath `"""' "", all
        findfile twoway_pgf_bridge.py
        local bridge "`r(fn)'"
        python script "`bridge'", args("`specpath'" "`settings'" "`timeout'" "`manifestdir'" "`texbin'")
        exit
    }
    if !inlist("`charttype'", "line", "waterfall", "bar", "scatter", "hexbin") {
        di as error "twoway_pgf: first argument must be the chart type: line, waterfall, bar, scatter or hexbin"
        di as error "         got: `charttype'"

        exit 198
    }
    syntax anything [if] [in] ,          ///
        NAMe(string)                     ///
        OUTdir(string)                   ///
        YTItle(string)                   ///
        [                                ///
        XTItle(string)                   ///
        LABels(string)                   ///
        COLors(string)                   ///
        PATterns(string)                 ///
        ALPhas(string)                   ///
        XLABel(string asis)              ///
        YLABel(string asis)              ///
        XRANge(string)                   ///
        YRANge(string)                   ///
        XLIne(numlist)                   ///
        LEGENDCols(integer 0)            ///
        LEGENDOrder(string)              ///
        NOLEGend                         ///
        SEPARATELEG                      ///
        EMPHasis(varname)                ///
        XTITLELeft(string)               ///
        XTITLERight(string)              ///
        FORmats(string)               ///
        SETTINGS(string)                 ///
        TIMEOUT(real 600)                ///
        MANIFESTdir(string)                 ///
        KINDs(string)                    ///
        SDVars(string)                   ///
        WHEre(string)                    ///
        NOREDuce                         ///
        NOVALUELabels                    ///
        LEGENDSize(string)               ///
        CATegory(varname)                ///
        CATLabel(varname)                ///
        GRoup(varname)                   ///
        GRPLabel(varname)                ///
        SERies(varname)                  ///
        SERLabel(varname)                ///
        SE(varname)                      ///
        LOwer(varname)                   ///
        UPper(varname)                   ///
        SEOn(string)                     ///
        BARWidth(real 0)                 ///
        GROUPGap(real 0)                 ///
        BASEline(real 0)                 ///
        SYMbols(string)                  ///
        MSIZes(string)                   ///
        RASTERize(string)                ///
        RASTERDpi(real 0)                ///
        BINS(integer 0)                  ///
        SRAnge(numlist min=2 max=2)      ///
        SIZEScale(string)                ///
        NOSIZEprop                       ///
        RAMP(string)                     ///
        CSCale(string)                   ///
        KEYMode(string)                  ///
        KEYSTEps(integer 0)              ///
        KEYTIcks(numlist)                ///
        KEYTITle(string)                 ///
        CUTs(numlist)                    ///
        ]
    if "`manifestdir'" == "" local manifestdir "`outdir'/manifests"
    python query
    tempfile datapath specpath
    if inlist("`charttype'", "line", "scatter") {
        local nvars : word count `anything'
        if `nvars' < 2 {
            di as error "twoway_pgf `charttype': need at least one y variable and one x variable"

            exit 198
        }
        local xvar : word `nvars' of `anything'
        local yvars ""
        forval i = 1/`=`nvars' - 1' {
            local yvars "`yvars' `: word `i' of `anything''"
        }
        local keepvars `yvars' `xvar'
    }
    else if "`charttype'" == "hexbin" {
        local nvars : word count `anything'
        if `nvars' != 2 {
            di as error "twoway_pgf hexbin: give exactly TWO variables, y then x"
            di as error "                (the same order as hexplot):"
            di as error "                  twoway_pgf hexbin ysim xobs , bins(20) ..."
            di as error "                got `nvars': `anything'"

            exit 198
        }
        local yvars : word 1 of `anything'
        local xvar  : word 2 of `anything'
        local keepvars `yvars' `xvar'
    }
    else if "`charttype'" == "bar" {
        local nvars : word count `anything'
        if `nvars' != 1 {
            di as error "twoway_pgf bar: give exactly ONE variable -- the column holding"
            di as error "             each segment's height. The category, group and"
            di as error "             series columns are named by options:"
            di as error "               twoway_pgf bar bar_share , category(bucket) ..."
            di as error "             got `nvars': `anything'"

            exit 198
        }
        local valuevar `anything'
        if "`category'" == "" {
            di as error "twoway_pgf bar: category() is required -- the column giving each"
            di as error "             bar's position, in plot order."

            exit 198
        }
        local yvars ""
        local xvar ""
        local keepvars `valuevar' `category' `catlabel' `group' `grplabel' ///
                       `series' `serlabel' `se' `lower' `upper'
    }
    else {
        local yvars `anything'
        local xvar ""
        local sdkeep ""
        foreach s of local sdvars {
            if !inlist("`s'", ".", "_none") local sdkeep "`sdkeep' `s'"
        }
        local wherecols ""
        local nw : word count `where'
        forval k = 1(2)`nw' {
            local wherecols "`wherecols' `: word `k' of `where''"
        }
        local keepvars `yvars' `sdkeep' `wherecols'
    }
    local barblock ""
    if "`charttype'" == "bar" {
        if "`seon'" == "" & ("`se'" != "" | "`lower'" != "" | "`upper'" != "") {
            local seon "total"
        }
        foreach opt in value category catlabel group grplabel series serlabel se lower upper seon {
            if "`opt'" == "value" local v "`valuevar'"
            else                  local v "``opt''"
            if "`v'" != "" local barblock "`barblock' `opt'=`v'"
        }
        foreach opt in barwidth groupgap baseline {
            if ``opt'' != 0 local barblock "`barblock' `opt'=``opt''"
        }
        noi di as text "twoway_pgf: bar options ->`barblock'"
    }
    local hexblock ""
    if "`charttype'" == "hexbin" {
        if `bins' != 0      local hexblock "`hexblock' bins=`bins'"
        if `keysteps' != 0  local hexblock "`hexblock' keysteps=`keysteps'"
        foreach opt in sizescale ramp cscale keymode {
            if "``opt''" != "" {
                local v : subinstr local `opt' " " "|", all
                local hexblock "`hexblock' `opt'=`v'"
            }
        }
        foreach opt in srange keyticks cuts {
            if "``opt''" != "" {
                local v : subinstr local `opt' " " "|", all
                local hexblock "`hexblock' `opt'=`v'"
            }
        }
        if `"`keytitle'"' != "" {
            if strpos(`"`keytitle'"', "|") {
                di as error "twoway_pgf hexbin: keytitle() cannot contain a pipe"
                di as error "                character -- it is the internal"
                di as error "                separator for packed options."

                exit 198
            }
            local v : subinstr local keytitle " " "|", all
            local hexblock "`hexblock' keytitle=`v'"
        }
        if "`nosizeprop'" != "" local hexblock "`hexblock' nosizeprop=1"
        noi di as text "twoway_pgf: hexbin options ->`hexblock'"
    }
    preserve
    if `"`if'`in'"' != "" {
        qui keep `if' `in'
    }
    qui keep `keepvars'
    local datefmt ""
    foreach v of local keepvars {
        local f : format `v'
        if substr("`f'", 1, 2) == "%t" | substr("`f'", 1, 3) == "%-t" {
            local datefmt `datefmt' `v'
            format `v' %20.0g
        }
    }
    if "`datefmt'" != "" {
        noi di as text "twoway_pgf: exporting `datefmt' as plain numbers " ///
            "(a %t format would export as text); give the ticks their "  ///
            "labels through the paired form of xlabel()"
    }
    qui count
    local nrows = r(N)
    noi di as text "twoway_pgf: exporting `nrows' rows x `: word count `keepvars'' cols"
    noi di as text "         -> `datapath'"
    qui export delimited using "`datapath'" , delimiter(",") nolabel replace
    restore
    _twoway_pgf_write_spec                            ///
        `charttype' `"`specpath'"' `"`datapath'"'  ///
        `"`name'"' `"`outdir'"'                    ///
        `"`ytitle'"' `"`xtitle'"'                  ///
        `"`yvars'"' `"`xvar'"'                     ///
        `"`labels'"' `"`colors'"' `"`patterns'"'   ///
        `"`alphas'"'                               ///
        `"`xlabel'"' `"`ylabel'"'                  ///
        `"`xrange'"' `"`yrange'"' `"`xline'"'      ///
        `legendcols' `"`legendorder'"'             ///
        `"`formats'"' `"`kinds'"' `"`sdvars'"'    ///
        `"`where'"'                       ///
        `"`noreduce'"' `"`novaluelabels'"'         ///
        `"`legendsize'"'                           ///
        `"`barblock'"'                             ///
        `"`symbols'"' `"`msizes'"'                 ///
        `"`rasterize'"' `rasterdpi'         ///
        `"`nolegend'"'                            ///
        `"`xtitleleft'"' `"`xtitleright'"' ///
        `"`emphasis'"'                            ///
        `"`hexblock'"'                            ///
        `"`separateleg'"'
    noi di as text "twoway_pgf: calling the backend"
    findfile twoway_pgf_bridge.py
    local bridge "`r(fn)'"
    python script "`bridge'", args("`specpath'" "`settings'" "`timeout'" "`manifestdir'" "`texbin'")
    noi di as result "twoway_pgf: done -- `name'"
end
program define _twoway_pgf_ticklist , sclass
    version 16
    sreturn clear
    args raw
    if `"`raw'"' == "" {
        sreturn local positions ""
        sreturn local labels ""
        exit 0
    }
    if strpos(`"`raw'"', `"""') == 0 {
        numlist `"`raw'"'
        sreturn local positions "`r(numlist)'"
        sreturn local labels ""
        exit 0
    }
    local positions ""
    local labels ""
    local rest `"`raw'"'
    local n 0
    while `"`rest'"' != "" {
        gettoken pos rest : rest
        gettoken lab rest : rest
        if missing(real("`pos'")) {
            di as error "twoway_pgf: in xlabel()/ylabel(), {bf:`pos'} is not a number."
            di as error `"         The paired form is: 432 "5000" 1432 "4000" ..."'"

            exit 198
        }
        if `"`lab'"' == "" {
            di as error "twoway_pgf: tick position `pos' has no label text."
            di as error "         In the paired form EVERY position needs one --"
            di as error "         matplotlib requires one label per tick, and"
            di as error "         inventing the rest would mean guessing a format."
            di as error "         Either label them all, or drop the labels and"
            di as error "         pass positions only."

            exit 198
        }
        local ++n
        local positions "`positions' `pos'"
        local labels `"`labels' "`lab'""'
    }
    sreturn local positions "`positions'"
    sreturn local labels `"`labels'"'
end
program define _twoway_pgf_range , sclass
    version 16
    sreturn clear
    args raw which
    local n : word count `raw'
    if `n' != 2 {
        di as error "twoway_pgf: `which'() takes exactly two values, got `n': `raw'"
        di as error "         Use . for a bound that should come from the data,"
        di as error "         e.g. `which'(-150 .) or `which'(. 10)."

        exit 198
    }
    local out_lo ""
    local out_hi ""
    local i 0
    foreach tok of local raw {
        local ++i
        if inlist("`tok'", ".", "_none") {
            local this "null"
        }
        else {
            _twoway_pgf_jsonnum "`tok'"
            local this "`s(jn)'"
        }
        if `i' == 1 local out_lo "`this'"
        else        local out_hi "`this'"
    }
    if "`out_lo'" == "null" & "`out_hi'" == "null" {
        di as error "twoway_pgf: `which'(. .) says nothing -- omit the option to"
        di as error "         take both ends from the data."

        exit 198
    }
    sreturn clear
    sreturn local lo "`out_lo'"
    sreturn local hi "`out_hi'"
end
program define _twoway_pgf_write_spec
    version 16
    args charttype specpath datapath name outdir ytitle xtitle ///
         yvars xvar labels colors patterns alphas xlabel ylabel      ///
         xrange yrange xline legendcols legendorder formats         ///
         kinds sdvars where noreduce novaluelabels            ///
         legendsize barblock symbols msizes rasterize rasterdpi     ///
         nolegend xtitleleft xtitleright emphasis hexblock ///
         separateleg
    local rest `"`barblock'"'
    while `"`rest'"' != "" {
        gettoken pair rest : rest
        local eq = strpos("`pair'", "=")
        if `eq' == 0 {
            di as error "twoway_pgf: internal -- bar option {bf:`pair'} is not key=value."

            exit 198
        }
        local k = substr("`pair'", 1, `eq' - 1)
        local bar_`k' = substr("`pair'", `eq' + 1, .)
    }
    local rest `"`hexblock'"'
    while `"`rest'"' != "" {
        gettoken pair rest : rest
        local eq = strpos("`pair'", "=")
        if `eq' == 0 {
            di as error "twoway_pgf: internal -- hexbin option {bf:`pair'} is not key=value."

            exit 198
        }
        local k = substr("`pair'", 1, `eq' - 1)
        local hex_`k' = substr("`pair'", `eq' + 1, .)
    }
    local rest `"`labels'"'
    local nlab 0
    while `"`rest'"' != "" {
        gettoken tok rest : rest
        local ++nlab
        local lab`nlab' `"`tok'"'
    }
    if `nlab' > 0 & inlist("`charttype'", "line", "scatter") {
        local nseries : word count `yvars'
        if `nlab' != `nseries' {
            di as error "twoway_pgf `charttype': labels() has `nlab' label(s) but there"
            di as error "                     are `nseries' series."
            di as error ""
            di as error "  Labels as parsed:"
            forvalues i = 1/`nlab' {
                di as error `"    `i'. [`lab`i'']"'
            }
            di as error ""
            di as error "  A count HIGHER than the series count almost always means"
            di as error "  the labels were word-split. syntax strips the quotes from"
            di as error "  a plain labels() value, so a two-word label becomes two"
            di as error "  labels and the boundaries are gone."
            di as error ""
            di as error "  Wrap the value in COMPOUND quotes so they survive. For"
            di as error "  the exact idiom see the package README."

            exit 198
        }
    }
    tempname fh
    file open `fh' using "`specpath'" , write replace text
    file write `fh' "{" _n
    file write `fh' `"  "spec": {"' _n
    file write `fh' `"    "schema": 1,"' _n
    file write `fh' `"    "type": "`charttype'","' _n
    foreach f in name outdir data {
        if "`f'" == "data" local v "`datapath'"
        else               local v "``f''"
        _twoway_pgf_jsonstr "`v'"
        file write `fh' `"    "`f'": "`s(js)'","' _n
    }
    _twoway_pgf_jsonstr "`ytitle'"
    file write `fh' `"    "ytitle": "`s(js)'","' _n
    if "`xtitle'" == "" {
        file write `fh' `"    "xtitle": null,"' _n
    }
    else {
        _twoway_pgf_jsonstr "`xtitle'"
        file write `fh' `"    "xtitle": "`s(js)'","' _n
    }
    foreach pair in xrange:xlim yrange:ylim {
        gettoken src rest : pair , parse(":")
        local dst = substr("`rest'", 2, .)
        local v "``src''"
        if "`v'" != "" {
            _twoway_pgf_range "`v'" "`src'"
            file write `fh' `"    "`dst'": [`s(lo)', `s(hi)'],"' _n
        }
    }
    foreach pair in xlabel:xticks ylabel:yticks {
        gettoken src rest : pair , parse(":")
        local dst = substr("`rest'", 2, .)
        local v `"``src''"'
        if `"`v'"' != "" {
            _twoway_pgf_ticklist `"`v'"'
            local positions "`s(positions)'"
            local ticklabels `"`s(labels)'"'
            file write `fh' `"    "`dst'": ["'
            local first 1
            foreach t of local positions {
                if `first' == 0 file write `fh' ", "
                _twoway_pgf_jsonnum "`t'"
                file write `fh' "`s(jn)'"
                local first 0
            }
            file write `fh' "],"  _n
            if `"`ticklabels'"' != "" {
                local axisletter = substr("`src'", 1, 1)
                file write `fh' `"    "`axisletter'tick_labels": ["'
                local first 1
                local rest2 `"`ticklabels'"'
                while `"`rest2'"' != "" {
                    gettoken one rest2 : rest2
                    if `first' == 0 file write `fh' ", "
                    _twoway_pgf_jsonstr `"`one'"'
                    file write `fh' `""`s(js)'""'
                    local first 0
                }
                file write `fh' "],"  _n
            }
        }
    }
    if "`noreduce'" != "" file write `fh' `"    "reduce": false,"' _n
    if "`formats'" != "" {
        file write `fh' `"    "formats": ["'
        local first 1
        foreach p of local formats {
            if `first' == 0 file write `fh' ", "
            file write `fh' `""`p'""'
            local first 0
        }
        file write `fh' "],"  _n
    }
    if "`xline'" != "" {
        file write `fh' `"    "reference_lines": ["' _n
        local first 1
        foreach v of local xline {
            if `first' == 0 file write `fh' "," _n
            _twoway_pgf_jsonnum "`v'"
            file write `fh' `"      {"axis": "x", "at": `s(jn)'}"'
            local first 0
        }
        file write `fh' _n `"    ],"' _n
    }
    if `"`xtitleleft'"' != "" {
        _twoway_pgf_jsonstr `"`xtitleleft'"'
        file write `fh' `"    "xtitle_left": "`s(js)'","' _n
    }
    if `"`xtitleright'"' != "" {
        _twoway_pgf_jsonstr `"`xtitleright'"'
        file write `fh' `"    "xtitle_right": "`s(js)'","' _n
    }
    if "`nolegend'" != "" {
        file write `fh' `"    "legend": {"show": false},"' _n
    }
    else if `legendcols' > 0 | "`legendorder'" != "" | "`legendsize'" != "" ///
            | "`separateleg'" != "" {
        file write `fh' `"    "legend": {"'
        local lfirst 1
        if "`separateleg'" != "" {
            file write `fh' `""position": "separate""'
            local lfirst 0
        }
        if `legendcols' > 0 {
            if `lfirst' == 0 file write `fh' ", "
            file write `fh' `""cols": `legendcols'"'
            local lfirst 0
        }
        if "`legendsize'" != "" {
            if `lfirst' == 0 file write `fh' ", "
            if missing(real("`legendsize'")) {
                file write `fh' `""fontsize": "`legendsize'""'
            }
            else {
                _twoway_pgf_jsonnum "`legendsize'"
                file write `fh' `""fontsize": `s(jn)'"'
            }
            local lfirst 0
        }
        if "`legendorder'" != "" {
            if `lfirst' == 0 file write `fh' ", "
            file write `fh' `""order": ["'
            local first 1
            foreach o of local legendorder {
                if `first' == 0 file write `fh' ", "
                if "`o'" == "blank" file write `fh' `""blank""'
                else {
                    _twoway_pgf_jsonnum "`o'"
                    file write `fh' "`s(jn)'"
                }
                local first 0
            }
            file write `fh' "]"
        }
        file write `fh' "},"  _n
    }
    if "`charttype'" == "line" {
        _twoway_pgf_jsonstr "`xvar'"
        if "`emphasis'" != "" {
            file write `fh' `"    "emphasis": "`emphasis'","' _n
        }
        file write `fh' `"    "x": "`s(js)'","' _n
        file write `fh' `"    "series": ["' _n
        local i 0
        foreach y of local yvars {
            local ++i
            if `i' > 1 file write `fh' "," _n
            file write `fh' `"      {"y": "`y'""'
            local lab `"`lab`i''"'
            if `"`lab'"' != "" {
                _twoway_pgf_jsonstr `"`lab'"'
                file write `fh' `", "label": "`s(js)'""'
            }
            local col : word `i' of `colors'
            if "`col'" != "" file write `fh' `", "color": "`col'""'
            local pat : word `i' of `patterns'
            if "`pat'" != "" file write `fh' `", "pattern": "`pat'""'
            local alp : word `i' of `alphas'
            if !inlist("`alp'", "", ".", "_none") {
                _twoway_pgf_jsonnum "`alp'"
                file write `fh' `", "alpha": `s(jn)'"'
            }
            file write `fh' "}"
        }
        file write `fh' _n `"    ]"' _n
    }
    else if "`charttype'" == "hexbin" {
        _twoway_pgf_jsonstr "`xvar'"
        file write `fh' `"    "x": "`s(js)'","' _n
        _twoway_pgf_jsonstr "`yvars'"
        file write `fh' `"    "y": "`s(js)'","' _n
        foreach k in sizescale ramp cscale keymode {
            if "`hex_`k''" != "" {
                if "`k'" == "sizescale" local jkey "size_scale"
                else if "`k'" == "cscale" local jkey "color_scale"
                else if "`k'" == "keymode" local jkey "key_mode"
                else local jkey "`k'"
                if "`k'" == "ramp" {
                    local vals : subinstr local hex_ramp "|" " ", all
                    file write `fh' `"    "ramp": ["'
                    local first 1
                    foreach t of local vals {
                        if `first' == 0 file write `fh' ", "
                        file write `fh' `""`t'""'
                        local first 0
                    }
                    file write `fh' "]," _n
                }
                else {
                    file write `fh' `"    "`jkey'": "`hex_`k''","' _n
                }
            }
        }
        foreach k in bins keysteps {
            if "`hex_`k''" != "" {
                if "`k'" == "keysteps" local jkey "key_steps"
                else local jkey "bins"
                file write `fh' `"    "`jkey'": `hex_`k'',"' _n
            }
        }
        if "`hex_keytitle'" != "" {
            local ktitle : subinstr local hex_keytitle "|" " ", all
            _twoway_pgf_jsonstr `"`ktitle'"'
            file write `fh' `"    "key_title": "`s(js)'","' _n
        }
        if "`hex_nosizeprop'" != "" {
            file write `fh' `"    "sizeprop": false,"' _n
        }
        foreach k in srange keyticks cuts {
            if "`hex_`k''" != "" {
                if "`k'" == "keyticks" local jkey "key_ticks"
                else                   local jkey "`k'"
                local vals : subinstr local hex_`k' "|" " ", all
                file write `fh' `"    "`jkey'": ["'
                local first 1
                foreach t of local vals {
                    if `first' == 0 file write `fh' ", "
                    _twoway_pgf_jsonnum "`t'"
                    file write `fh' "`s(jn)'"
                    local first 0
                }
                file write `fh' "]," _n
            }
        }
        file write `fh' `"    "value": null"' _n
    }
    else if "`charttype'" == "scatter" {
        _twoway_pgf_jsonstr "`xvar'"
        file write `fh' `"    "x": "`s(js)'","' _n
        file write `fh' `"    "series": ["' _n
        local i 0
        foreach y of local yvars {
            local ++i
            if `i' > 1 file write `fh' "," _n
            file write `fh' `"      {"y": "`y'""'
            local lab `"`lab`i''"'
            if `"`lab'"' != "" {
                _twoway_pgf_jsonstr `"`lab'"'
                file write `fh' `", "label": "`s(js)'""'
            }
            local col : word `i' of `colors'
            if "`col'" != "" file write `fh' `", "color": "`col'""'
            local sym : word `i' of `symbols'
            if !inlist("`sym'", "", ".", "_none") {
                file write `fh' `", "symbol": "`sym'""'
            }
            local msz : word `i' of `msizes'
            if !inlist("`msz'", "", ".", "_none") {
                if missing(real("`msz'")) {
                    file write `fh' `", "size": "`msz'""'
                }
                else {
                    _twoway_pgf_jsonnum "`msz'"
                    file write `fh' `", "size": `s(jn)'"'
                }
            }
            local alp : word `i' of `alphas'
            if !inlist("`alp'", "", ".", "_none") {
                _twoway_pgf_jsonnum "`alp'"
                file write `fh' `", "alpha": `s(jn)'"'
            }
            file write `fh' "}"
        }
        file write `fh' _n `"    ]"' _n
        if "`rasterize'" != "" {
            if !inlist(lower("`rasterize'"), "on", "off", "auto", "yes", "no") {
                di as error "twoway_pgf: rasterize() takes on, off or auto; got {bf:`rasterize'}"

                exit 198
            }
            if inlist(lower("`rasterize'"), "on", "yes") {
                file write `fh' `"    ,"rasterize": true"' _n
            }
            else if inlist(lower("`rasterize'"), "off", "no") {
                file write `fh' `"    ,"rasterize": false"' _n
            }
        }
        if `rasterdpi' > 0 {
            _twoway_pgf_jsonnum "`rasterdpi'"
            file write `fh' `"    ,"raster_dpi": `s(jn)'"' _n
        }
    }
    else if "`charttype'" == "bar" {
        local bfirst 1
        foreach k in category value catlabel group grplabel series serlabel se lower upper seon {
            if "`bar_`k''" != "" {
                local field "`k'"
                if "`k'" == "catlabel" local field "category_label"
                if "`k'" == "grplabel" local field "group_label"
                if "`k'" == "serlabel" local field "series_label"
                if "`k'" == "seon"     local field "se_on"
                if `bfirst' == 0 file write `fh' "," _n
                _twoway_pgf_jsonstr "`bar_`k''"
                file write `fh' `"    "`field'": "`s(js)'""'
                local bfirst 0
            }
        }
        foreach k in barwidth groupgap baseline {
            if "`bar_`k''" != "" {
                local field "`k'"
                if "`k'" == "barwidth" local field "bar_width"
                if "`k'" == "groupgap" local field "group_gap"
                if `bfirst' == 0 file write `fh' "," _n
                _twoway_pgf_jsonnum "`bar_`k''"
                file write `fh' `"    "`field'": `s(jn)'"'
                local bfirst 0
            }
        }
        if "`colors'" != "" {
            if `bfirst' == 0 file write `fh' "," _n
            file write `fh' `"    "colors": ["'
            local first 1
            foreach c of local colors {
                if `first' == 0 file write `fh' ", "
                _twoway_pgf_jsonstr "`c'"
                file write `fh' `""`s(js)'""'
                local first 0
            }
            file write `fh' "]"
            local bfirst 0
        }
        file write `fh' _n
    }
    else {
        if "`novaluelabels'" != "" {
            noi di as text "twoway_pgf: novaluelabels is now the default and " ///
                "has no effect; bar values are never printed."
        }
        if "`where'" != "" {
            file write `fh' `"    "row_filter": {"'
            local nw : word count `where'
            local first 1
            forval k = 1(2)`nw' {
                local col : word `k' of `where'
                local val : word `=`k' + 1' of `where'
                if `first' == 0 file write `fh' ", "
                file write `fh' `""`col'": "`val'""'
                local first 0
            }
            file write `fh' "},"  _n
        }
        file write `fh' `"    "bars": ["' _n
        local i 0
        foreach v of local yvars {
            local ++i
            if `i' > 1 file write `fh' "," _n
            local lab `"`lab`i''"'
            if `"`lab'"' == "" local lab "`v'"
            _twoway_pgf_jsonstr `"`lab'"'
            file write `fh' `"      {"value_col": "`v'", "label": "`s(js)'""'
            local knd : word `i' of `kinds'
            if "`knd'" != "" file write `fh' `", "kind": "`knd'""'
            local sdv : word `i' of `sdvars'
            if !inlist("`sdv'", "", ".", "_none") {
                file write `fh' `", "sd_col": "`sdv'""'
            }
            file write `fh' "}"
        }
        file write `fh' _n `"    ]"' _n
    }
    file write `fh' "  }" _n
    file write `fh' "}" _n
    file close `fh'
    noi di as text "twoway_pgf: wrote spec -> `specpath'"
end
program define _twoway_pgf_jsonstr , sclass
    version 16
    args str
    local out = subinstr(`"`str'"', "\", "\\", .)
    local out = subinstr(`"`out'"', char(34), "\" + char(34), .)
    sreturn local js `"`out'"'
end
program define _twoway_pgf_jsonnum , sclass
    version 16
    args tok
    sreturn clear
    local t = trim("`tok'")
    if missing(real("`t'")) {
        di as error "twoway_pgf: {bf:`tok'} is not a number."
        di as error "         xrange()/yrange()/xlabel()/ylabel()/xline()/alphas()"
        di as error "         take numeric values only (Stata missing values included)."

        exit 198
    }
    if substr("`t'", 1, 1)  == "+"  local t = substr("`t'", 2, .)
    if substr("`t'", 1, 1)  == "."  local t = "0" + "`t'"
    if substr("`t'", 1, 2)  == "-." local t = "-0" + substr("`t'", 2, .)
    if substr("`t'", -1, 1) == "."  local t = "`t'" + "0"
    if real("`t'") != real(trim("`tok'")) {
        di as error "twoway_pgf: internal -- normalising {bf:`tok'} changed its value to {bf:`t'}."

        exit 198
    }
    if !regexm("`t'", "^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$") {
        di as error "twoway_pgf: cannot write {bf:`tok'} as a JSON number (got {bf:`t'})."

        exit 198
    }
    sreturn local jn "`t'"
end
