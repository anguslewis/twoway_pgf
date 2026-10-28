import re
_ESCAPES = [('\\', '\\textbackslash{}'), ('&', '\\&'), ('%', '\\%'), ('$', '\\$'), ('#', '\\#'), ('_', '\\_'), ('{', '\\{'), ('}', '\\}'), ('~', '\\textasciitilde{}'), ('^', '\\textasciicircum{}')]
_NEEDS_ESCAPE_OUTSIDE_MATH = {'_', '&', '#'}

def escape(text):
    if text is None:
        return None
    replacements = dict(_ESCAPES)
    return ''.join(replacements.get(char, char) for char in str(text))
SMCL_GLYPHS = {'{&larr}': '\\(\\leftarrow\\)', '{&rarr}': '\\(\\rightarrow\\)', '{&uarr}': '\\(\\uparrow\\)', '{&darr}': '\\(\\downarrow\\)', '{&harr}': '\\(\\leftrightarrow\\)', '{&lArr}': '\\(\\Leftarrow\\)', '{&rArr}': '\\(\\Rightarrow\\)', '{&uArr}': '\\(\\Uparrow\\)', '{&dArr}': '\\(\\Downarrow\\)', '{&hArr}': '\\(\\Leftrightarrow\\)'}

def translate_glyphs(text):
    if text is None:
        return None
    out = str(text)
    for entity, latex in SMCL_GLYPHS.items():
        out = out.replace(entity, latex)
    out = re.sub(' {2,}', lambda m: '{ }' * len(m.group(0)), out)
    return out

def validate(text, field='text'):
    if text is None:
        return None
    string = str(text)
    in_math = False
    depth = 0
    index = 0
    while index < len(string):
        char = string[index]
        if char == '\\':
            following = string[index + 1:index + 2]
            if following in ('(', '['):
                if in_math:
                    raise ValueError(f"{field}: '\\{following}' opens maths inside maths at position {index} in {string!r}.")
                in_math = True
            elif following in (')', ']'):
                if not in_math:
                    raise ValueError(f"{field}: '\\{following}' closes maths that was never opened, at position {index} in {string!r}.")
                in_math = False
            index += 2
            continue
        if char == '$':
            in_math = not in_math
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth < 0:
                raise ValueError(f"{field}: unbalanced '}}' at position {index} in {string!r}. Text fields are raw LaTeX; brace it correctly or run the string through twoway_pgf.texesc.escape().")
        elif not in_math and char in _NEEDS_ESCAPE_OUTSIDE_MATH:
            raise ValueError(f"{field}: unescaped '{char}' outside maths mode at position {index} in {string!r}. Text fields are raw LaTeX, so this would break the paper's compile. Write '\\{char}', put it in maths mode, or run the string through twoway_pgf.texesc.escape().")
        index += 1
    if in_math:
        raise ValueError(f"{field}: maths mode is never closed in {string!r} (odd number of '$', or a '\\(' / '\\[' with no matching '\\)' / '\\]'). This will break the paper's compile.")
    if depth != 0:
        raise ValueError(f"{field}: {depth} unclosed '{{' in {string!r}.")
    return string

def unescape_newlines(text):
    if text is None:
        return None
    return str(text).replace('\\n', '\n')

def validate_all(items):
    for field, text in items.items():
        if text is None:
            continue
        if isinstance(text, (list, tuple)):
            for position, element in enumerate(text):
                validate(element, field=f'{field}[{position}]')
        else:
            validate(text, field=field)
