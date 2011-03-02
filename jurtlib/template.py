from string import Template

def template_expand(templ, vars):
    templ = Template(templ)
    return templ.substitute(vars)
