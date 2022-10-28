
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

def len_to_str(l, limit=10):
    return str(l) + '+' if l > limit else str(l) if l else ''

def add_query_ex(values, include_path=True):
    new_args = [(k, v) for k, v in dict(flask.request.args, **values).items()
                       if v is not None]
    new_query = '?' + urllib.parse.urlencode(new_args)
    if not include_path:
        return new_query
    elif new_args:
        return flask.request.root_path + flask.request.path + new_query
    else:
        return flask.request.root_path + flask.request.path
def add_query(**values):
    return add_query_ex(values)

def render_timestamp(ts):
    parts = time.gmtime(ts)
    return Markup('<time datetime="%s" class="localize">%s</time>' % (
        time.strftime('%Y-%m-%dT%H:%M:%SZ', parts),
        time.strftime('%Y-%m-%d %H:%M:%S UTC', parts)
    ))

def render_pagination(offset, page_size, cur_page_size, offset_var='offset'):
    if offset == 0 and cur_page_size <= page_size:
        return Markup(
            '<div class="pagination null-pagination mx-auto"></div>'
        )

    more_av = (cur_page_size + offset % page_size > page_size)
    cp, po = divmod(offset, page_size)
    pages = []
    pages.append((max(0, (offset - 1) // page_size * page_size),
                  '\u2039 Previous',
                  (offset > 0)))
    if cp >= 2: pages.append((0, '1', True))
    if cp >= 3: pages.append((page_size, '2', True))
    if cp >= 4: pages.append((None, '...', False))
    if cp >= 1: pages.append(((cp - 1) * page_size, str(cp), True))
    pages.append((cp * page_size, str(cp + 1), True))
    if po != 0: pages.append((offset,
                              '%d.%d' % (cp + 1, po * 10 // page_size),
                              True))
    if more_av: pages.append(((cp + 1) * page_size, str(cp + 2), True))
    pages.append(((cp + 1) * page_size, 'Next \u203a', more_av))

    result = [
        Markup('<ul class="pagination justify-content-center mb-0 mx-auto">')
    ]
    for o, t, e in pages:
        if not e:
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

def render_sortctl(label, keyword, default=None, query_var='sort'):
    cur_value = flask.request.args.get(query_var, default)
    if cur_value == keyword:
        link = add_query_ex({query_var: '-' + keyword})
        arrow = '\u2193'
        tooltip = '(sorted normally; click to reverse)'
    else:
        link = add_query_ex({query_var: keyword})
        if cur_value == '-' + keyword:
            arrow = '\u2191'
            tooltip = '(sorted in reverse; click to sort normally)'
        else:
            arrow = '\u2195'
            tooltip = '(not sorted; click to sort)'
    result = [Markup('<a class="sort-control" href="%s" title="%s" '
                        'data-bs-toggle="tooltip">') %
              (link, tooltip)]
    if label:
        result.extend((label, ' '))
    result.append(arrow)
    result.append(Markup('</a>'))
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

    result.append(Markup('</form>'))
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
