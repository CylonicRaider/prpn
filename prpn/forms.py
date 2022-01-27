
from markupsafe import Markup, escape

DEFAULT_METHOD = 'POST'
DEFAULT_ENCTYPE = 'application/x-www-form-urlencoded'

def render_form(action, fields, method=None, enctype=None):
    if method is None: method = DEFAULT_METHOD
    if enctype is None: enctype = DEFAULT_ENCTYPE
    result = [Markup('<form action="%s" method="%s" enctype="%s" '
                           'class="mini-form">\n') %
                  (action, method, enctype)]
    for record in fields:
        name, ftype, label = record[:3]
        value = None if len(record) == 3 else record[3]
        if ftype in ('submit', 'reset', 'button'):
            result.extend((
                Markup('  <div class="d-grid">\n'),
                Markup('    <input type="%s" id="%s" value="%s" '
                                  'class="btn btn-primary"/>\n') %
                    (ftype, name, label),
                Markup('  </div>\n')
            ))
        elif ftype in ('checkbox', 'radio'):
            result.extend((
                Markup('  <div class="form-check mb-3">\n'),
                Markup('    <input type="checkbox" id="%s" name="%s" ') %
                    (name, name),
                ('' if value is None else Markup('value="%s" ') % (value,)),
                Markup('class="form-check-input"/>\n'),
                Markup('  <label for="%s" '
                                'class="form-check-label">%s</label>') %
                    (name, label),
                Markup('  </div>\n')
            ))
        else:
            result.extend((
                Markup('  <div class="mb-3">\n'),
                Markup('    <label for="%s" '
                                  'class="form-label">%s</label>\n') %
                    (name, label),
                Markup('    <input type="%s" id="%s" name="%s" ') %
                    (ftype, name, name),
                ('' if value is None else Markup('value="%s" ') % (value,)),
                Markup('class="form-control"/>\n'),
                Markup('  </div>\n')
            ))
    result.append(Markup('</form>\n'))
    return Markup('').join(result)
