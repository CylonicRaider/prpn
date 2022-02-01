
from markupsafe import Markup, escape

DEFAULT_METHOD = 'post'
DEFAULT_ENCTYPE = 'application/x-www-form-urlencoded'

def render_form(title, action, fields, method=None, enctype=Ellipsis):
    def maybe_attr(name, value):
        return Markup(' %s="%s"' % (name, value)) if value is not None else ''

    if method is None: method = DEFAULT_METHOD
    if enctype is Ellipsis: enctype = DEFAULT_ENCTYPE

    result = [Markup('<form action="%s" method="%s"%s '
                           'class="mini-form mx-auto">') %
                  (action, method, maybe_attr('enctype', enctype))]

    if title is not None:
        result.append(Markup('  <h2>%s</h2>') % (title,) if title else '')

    for record in fields:
        if not record: continue
        name, ftype, label = record[:3]
        if name is None or len(record) == 3 or record[3] is None:
            value, value_attrs = None, ''
        else:
            value = record[3]
            value_attrs = Markup(' name="%s" value="%s"') % (name, value)

        if ftype in ('submit', 'reset', 'button'):
            result.extend((
                Markup('  <div class="d-grid">'),
                Markup('    <button type="%s"%s '
                                   'class="btn btn-primary">%s</button>') %
                    (ftype, value_attrs, label),
                Markup('  </div>')
            ))

        elif ftype in ('checkbox', 'radio'):
            result.extend((
                Markup('  <div class="form-check mb-3">'),
                Markup('    <input type="%s" id="%s"%s '
                                  'class="form-check-input"/>') %
                    (ftype, name, value_attrs),
                Markup('    <label for="%s" '
                                  'class="form-check-label">%s</label>') %
                    (name, label),
                Markup('  </div>')
            ))

        elif ftype == 'label':
            result.append(
                Markup('  <p class="mb-3"%s>%s</p>') %
                    (maybe_attr('id', name), label)
            )

        elif ftype == 'hidden':
            result.append(
                Markup('  <input type="hidden"%s%s/>') %
                    (maybe_attr('id', name), value_attrs)
            )

        else:
            result.extend((
                Markup('  <div class="mb-3">'),
                Markup('    <label for="%s" class="form-label">%s</label>') %
                    (name, label),
                Markup('    <input type="%s" id="%s" name="%s"%s '
                                  'class="form-control"/>') %
                    (ftype, name, name, maybe_attr('value', value)),
                Markup('  </div>')
            ))

    result.extend((Markup('</form>'), ''))
    return Markup('\n').join(result)
