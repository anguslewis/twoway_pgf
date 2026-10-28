"""Resolved final-size formats. Names have no implicit meaning."""
from copy import copy
from types import SimpleNamespace
from . import settings, style

class Format:
    def __init__(self,name,values):
        self.name=name
        for key,val in values.items():
            if key!='visual': setattr(self,key,val)
        self.layout=None if self.layout is None else SimpleNamespace(**self.layout)
        self.document=''
    def with_height(self,height_in):
        result=copy(self)
        result.height_in=height_in
        return result
    def rcparams(self):
        strokes=settings.value('strokes')
        return {'figure.figsize':(self.width_in,self.height_in),
          'font.family':self.font_family,'font.size':self.base_pt,
          'axes.labelsize':self.base_pt*self.axis_title_ratio,'axes.titlesize':self.base_pt,
          'xtick.labelsize':self.base_pt,'ytick.labelsize':self.base_pt,'legend.fontsize':self.base_pt,
          'legend.handlelength':style.legend_handlelength(self.base_pt),'pgf.preamble':self.tex_preamble,
          'axes.linewidth':style.linewidth_points(strokes['axes'])*self.ink_scale,
          'xtick.major.width':style.linewidth_points(strokes['ticks'])*self.ink_scale,
          'ytick.major.width':style.linewidth_points(strokes['ticks'])*self.ink_scale,
          'grid.linewidth':self.grid_linewidth}

def resolve(names):
    state=settings._STATE.get()
    if names is None: names=state['config']['default_formats']
    if isinstance(names,str): names=[names]
    if not isinstance(names,(list,tuple)) or not names: raise ValueError('formats must be a nonempty list of names')
    if len(set(names))!=len(names): raise ValueError('formats must be unique')
    result=[]
    for name in names:
        if name not in state['formats']: raise ValueError(f'{state["path"]}: unknown format {name!r}; available {list(state["formats"])}')
        result.append(Format(name,state['formats'][name]))
    return result
