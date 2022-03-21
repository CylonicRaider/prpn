
import time
import urllib.parse

import flask
from markupsafe import Markup, escape

DEFAULT_FORM_METHOD = 'post'
DEFAULT_FORM_ENCTYPE = 'application/x-www-form-urlencoded'

MAX_INT64 = 2 ** 63 - 1

def get_request_int64p(name, default=0):
    try:
        result = int(flask.request.args.get(name, str(default)), 10)
        if result < 0 or result > MAX_INT64:
            raise ValueError('Integer out of range')
    except ValueError:
        flask.abort(400)
        return None
    return result

def add_query_ex(values):
    new_args = [(k, v) for k, v in dict(flask.request.args, **values).items()
                       if v is not None]
    return '?' + urllib.parse.urlencode(new_args)
def add_query(**values):
    return add_query_ex(values)

def render_timestamp(ts):
    parts = time.gmtime(ts)
    return Markup('<time datetime="%s" class="localize">%s</time>' % (
        time.strftime('%Y-%m-%dT%H:%M:%SZ', parts),
        time.strftime('%Y-%m-%d %H:%M:%S UTC', parts)
    ))

def render_pagination(offset, page_size, has_more, offset_var='offset'):
    cp, po = divmod(offset, page_size)
    pages = []
    if cp >= 2: pages.append((0, '1'))
    if cp >= 3: pages.append((page_size, '2'))
    if cp >= 4: pages.append((None, '...'))
    if cp >= 1: pages.append(((cp - 1) * page_size, str(cp)))
    pages.append((cp * page_size, str(cp + 1)))
    if po != 0: pages.append((offset,
                              '%d.%d' % (cp + 1, po * 10 // page_size)))
    if has_more: pages.append(((cp + 1) * page_size, str(cp + 2)))

    result = [
        Markup('<ul class="pagination justify-content-center mb-0 mx-auto">')
    ]
    for o, t in pages:
        if o is None:
            result.append(Markup('<li class="page-item disabled">'
                                     '<span class="page-link">%s</span>'
                                 '</li>' % (t,)))
        else:
            result.append(Markup('<li class="page-item%s">'
                                   '<a class="page-link" href="%s">%s</a>'
                                 '</li>') %
                              ((' active' if o == offset else ''),
                               add_query_ex({offset_var: o}),
                               t))
    result.append(Markup('</ul>'))
    return Markup('').join(result)

def render_form(title, action, fields, method=Ellipsis, enctype=Ellipsis):
    def maybe_attr(name, value):
        return Markup(' %s="%s"' % (name, value)) if value is not None else ''

    if method is Ellipsis: method = DEFAULT_FORM_METHOD
    if enctype is Ellipsis: enctype = DEFAULT_FORM_ENCTYPE

    result = [Markup('<form action="%s"%s%s>') %
                  (action, maybe_attr('method', method),
                   maybe_attr('enctype', enctype))]

    if title is not None:
        result.append(Markup('  <h2>%s</h2>') % (title,) if title else '')

    has_autofocus = False
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
            aft = ''
            if ftype == 'text' and not has_autofocus:
                aft = Markup(' autofocus="autofocus"')
                has_autofocus = True
            result.extend((
                Markup('  <div class="mb-3">'),
                Markup('    <label for="%s" class="form-label">%s</label>') %
                    (name, label),
                Markup('    <input type="%s" id="%s" name="%s"%s%s '
                                  'class="form-control"/>') %
                    (ftype, name, name, maybe_attr('value', value), aft),
                Markup('  </div>')
            ))

    result.extend((Markup('</form>'), ''))
    return Markup('\n').join(result)

def execute_form_or_redirect(params, template_name, **template_params):
    code = params[0]
    if 200 <= code < 300:
        if len(params) == 2:
            text = params[1]
            return flask.render_template(template_name, form_content=text,
                                         **template_params)
        action, fields = params[1:3]
        method = params[3] if len(params) > 3 else Ellipsis
        enctype = params[4] if len(params) > 4 else Ellipsis
        form_content = render_form(None, action, fields, method, enctype)
        return flask.render_template(template_name, form_content=form_content,
                                     **template_params)
    elif 300 <= code < 400:
        location = params[1]
        return flask.redirect(location, code)
    else:
        return flask.abort(code)
