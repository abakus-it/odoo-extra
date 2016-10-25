# -*- coding: utf-8 -*-
import datetime
import hashlib
import itertools
import logging
import operator
from collections import OrderedDict

from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextToPath
import werkzeug

import openerp
from openerp import http, SUPERUSER_ID
from openerp.http import request
from openerp.osv import osv
from openerp.addons.website.models.website import slug
from openerp.addons.website_sale.controllers.main import QueryURL

_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# RunBot helpers
#----------------------------------------------------------

def s2human(time):
    """Convert a time in second into an human readable string"""
    for delay, desc in [(86400,'d'),(3600,'h'),(60,'m')]:
        if time >= delay:
            return str(int(time / delay)) + desc
    return str(int(time)) + "s"

def flatten(list_of_lists):
    return list(itertools.chain.from_iterable(list_of_lists))

def uniq_list(l):
    return OrderedDict.fromkeys(l).keys()


#----------------------------------------------------------
# Runbot Controller
#----------------------------------------------------------

class RunbotController(http.Controller):

    @http.route(['/runbot', '/runbot/repo/<model("runbot.repo"):repo>'], type='http', auth="public", website=True)
    def repo(self, repo=None, search='', limit='100', refresh='', **post):
        registry, cr, uid = request.registry, request.cr, request.uid

        branch_obj = registry['runbot.branch']
        build_obj = registry['runbot.build']
        icp = registry['ir.config_parameter']
        repo_obj = registry['runbot.repo']
        count = lambda dom: build_obj.search_count(cr, uid, dom)

        repo_ids = repo_obj.search(cr, uid, [])
        repos = repo_obj.browse(cr, uid, repo_ids)
        if not repo and repos:
            repo = repos[0]

        context = {
            'repos': repos,
            'repo': repo,
            'host_stats': [],
            'pending_total': count([('state','=','pending')]),
            'limit': limit,
            'search': search,
            'refresh': refresh,
        }

        build_ids = []
        if repo:
            filters = {key: post.get(key, '1') for key in ['pending', 'testing', 'running', 'done']}
            domain = [('repo_id','=',repo.id)]
            domain += [('state', '!=', key) for key, value in filters.iteritems() if value == '0']
            if search:
                domain += ['|', '|', ('dest', 'ilike', search), ('subject', 'ilike', search), ('branch_id.branch_name', 'ilike', search)]

            build_ids = build_obj.search(cr, uid, domain, limit=int(limit))
            branch_ids, build_by_branch_ids = [], {}

            if build_ids:
                branch_query = """
                SELECT br.id FROM runbot_branch br INNER JOIN runbot_build bu ON br.id=bu.branch_id WHERE bu.id in %s
                ORDER BY bu.sequence DESC
                """
                sticky_dom = [('repo_id','=',repo.id), ('sticky', '=', True)]
                sticky_branch_ids = [] if search else branch_obj.search(cr, uid, sticky_dom)
                cr.execute(branch_query, (tuple(build_ids),))
                branch_ids = uniq_list(sticky_branch_ids + [br[0] for br in cr.fetchall()])

                build_query = """
                    SELECT
                        branch_id,
                        max(case when br_bu.row = 1 then br_bu.build_id end),
                        max(case when br_bu.row = 2 then br_bu.build_id end),
                        max(case when br_bu.row = 3 then br_bu.build_id end),
                        max(case when br_bu.row = 4 then br_bu.build_id end)
                    FROM (
                        SELECT
                            br.id AS branch_id,
                            bu.id AS build_id,
                            row_number() OVER (PARTITION BY branch_id) AS row
                        FROM
                            runbot_branch br INNER JOIN runbot_build bu ON br.id=bu.branch_id
                        WHERE
                            br.id in %s
                        GROUP BY br.id, bu.id
                        ORDER BY br.id, bu.id DESC
                    ) AS br_bu
                    WHERE
                        row <= 4
                    GROUP BY br_bu.branch_id;
                """
                cr.execute(build_query, (tuple(branch_ids),))
                build_by_branch_ids = {
                    rec[0]: [r for r in rec[1:] if r is not None] for rec in cr.fetchall()
                }

            branches = branch_obj.browse(cr, uid, branch_ids, context=request.context)
            build_ids = flatten(build_by_branch_ids.values())
            build_dict = {build.id: build for build in build_obj.browse(cr, uid, build_ids, context=request.context) }

            def branch_info(branch):
                return {
                    'branch': branch,
                    'builds': [self.build_info(build_dict[build_id]) for build_id in build_by_branch_ids[branch.id]]
                }

            context.update({
                'branches': [branch_info(b) for b in branches],
                'testing': count([('repo_id','=',repo.id), ('state','=','testing')]),
                'running': count([('repo_id','=',repo.id), ('state','=','running')]),
                'pending': count([('repo_id','=',repo.id), ('state','=','pending')]),
                'qu': QueryURL('/runbot/repo/'+slug(repo), search=search, limit=limit, refresh=refresh, **filters),
                'filters': filters,
            })

        # consider host gone if no build in last 100
        build_threshold = max(build_ids or [0]) - 100

        for result in build_obj.read_group(cr, uid, [('id', '>', build_threshold)], ['host'], ['host']):
            if result['host']:
                context['host_stats'].append({
                    'host': result['host'],
                    'testing': count([('state', '=', 'testing'), ('host', '=', result['host'])]),
                    'running': count([('state', '=', 'running'), ('host', '=', result['host'])]),
                })

        return request.render("runbot.repo", context)

    @http.route(['/runbot/hook/<int:repo_id>'], type='http', auth="public", website=True)
    def hook(self, repo_id=None, **post):
        # TODO if repo_id == None parse the json['repository']['ssh_url'] and find the right repo
        repo = request.registry['runbot.repo'].browse(request.cr, SUPERUSER_ID, [repo_id])
        repo.hook_time = datetime.datetime.now().strftime(openerp.tools.DEFAULT_SERVER_DATETIME_FORMAT)
        return ""

    @http.route(['/runbot/dashboard'], type='http', auth="public", website=True)
    def dashboard(self, refresh=None):
        cr = request.cr
        RB = request.env['runbot.build']
        repos = request.env['runbot.repo'].search([])   # respect record rules

        cr.execute("""SELECT bu.id
                        FROM runbot_branch br
                        JOIN LATERAL (SELECT *
                                        FROM runbot_build bu
                                       WHERE bu.branch_id = br.id
                                    ORDER BY id DESC
                                       LIMIT 3
                                     ) bu ON (true)
                       WHERE br.sticky
                         AND br.repo_id in %s
                    ORDER BY br.repo_id, br.branch_name, bu.id DESC
                   """, [tuple(repos._ids)])

        builds = RB.browse(map(operator.itemgetter(0), cr.fetchall()))

        count = RB.search_count
        qctx = {
            'refresh': refresh,
            'host_stats': [],
            'pending_total': count([('state', '=', 'pending')]),
        }

        repos_values = qctx['repo_dict'] = OrderedDict()
        for build in builds:
            repo = build.repo_id
            branch = build.branch_id
            r = repos_values.setdefault(repo.id, {'branches': OrderedDict()})
            if 'name' not in r:
                r.update({
                    'name': repo.name,
                    'base': repo.base,
                    'testing': count([('repo_id', '=', repo.id), ('state', '=', 'testing')]),
                    'running': count([('repo_id', '=', repo.id), ('state', '=', 'running')]),
                    'pending': count([('repo_id', '=', repo.id), ('state', '=', 'pending')]),
                })
            b = r['branches'].setdefault(branch.id, {'name': branch.branch_name, 'builds': list()})
            b['builds'].append(self.build_info(build))

        # consider host gone if no build in last 100
        build_threshold = max(builds.ids or [0]) - 100
        for result in RB.read_group([('id', '>', build_threshold)], ['host'], ['host']):
            if result['host']:
                qctx['host_stats'].append({
                    'host': result['host'],
                    'testing': count([('state', '=', 'testing'), ('host', '=', result['host'])]),
                    'running': count([('state', '=', 'running'), ('host', '=', result['host'])]),
                })

        return request.render("runbot.sticky-dashboard", qctx)

    def build_info(self, build):
        real_build = build.duplicate_id if build.state == 'duplicate' else build
        return {
            'id': build.id,
            'name': build.name,
            'state': real_build.state,
            'result': real_build.result,
            'subject': build.subject,
            'author': build.author,
            'committer': build.committer,
            'dest': build.dest,
            'real_dest': real_build.dest,
            'job_age': s2human(real_build.job_age),
            'job_time': s2human(real_build.job_time),
            'job': real_build.job,
            'domain': real_build.domain,
            'host': real_build.host,
            'port': real_build.port,
            'subject': build.subject,
            'server_match': real_build.server_match,
            'duplicate_of': build.duplicate_id if build.state == 'duplicate' else False,
        }

    @http.route(['/runbot/build/<build_id>'], type='http', auth="public", website=True)
    def build(self, build_id=None, search=None, **post):
        registry, cr, uid, context = request.registry, request.cr, request.uid, request.context

        Build = registry['runbot.build']
        Logging = registry['ir.logging']

        build = Build.browse(cr, uid, [int(build_id)])[0]
        if not build.exists():
            return request.not_found()

        real_build = build.duplicate_id if build.state == 'duplicate' else build

        # other builds
        build_ids = Build.search(cr, uid, [('branch_id', '=', build.branch_id.id)])
        other_builds = Build.browse(cr, uid, build_ids)

        domain = ['|', ('dbname', '=like', '%s-%%' % real_build.dest), ('build_id', '=', real_build.id)]
        #if type:
        #    domain.append(('type', '=', type))
        #if level:
        #    domain.append(('level', '=', level))
        if search:
            domain.append(('name', 'ilike', search))
        logging_ids = Logging.search(cr, SUPERUSER_ID, domain)

        context = {
            'repo': build.repo_id,
            'build': self.build_info(build),
            'br': {'branch': build.branch_id},
            'logs': Logging.browse(cr, SUPERUSER_ID, logging_ids),
            'other_builds': other_builds
        }
        #context['type'] = type
        #context['level'] = level
        return request.render("runbot.build", context)

    @http.route(['/runbot/build/<build_id>/force'], type='http', auth="public", methods=['POST'], csrf=False)
    def build_force(self, build_id, **post):
        registry, cr, uid, context = request.registry, request.cr, request.uid, request.context
        repo_id = registry['runbot.build'].force(cr, uid, [int(build_id)])
        return werkzeug.utils.redirect('/runbot/repo/%s' % repo_id)

    @http.route([
        '/runbot/badge/<int:repo_id>/<branch>.svg',
        '/runbot/badge/<any(default,flat):theme>/<int:repo_id>/<branch>.svg',
    ], type="http", auth="public", methods=['GET', 'HEAD'])
    def badge(self, repo_id, branch, theme='default'):

        domain = [('repo_id', '=', repo_id),
                  ('branch_id.branch_name', '=', branch),
                  ('branch_id.sticky', '=', True),
                  ('state', 'in', ['testing', 'running', 'done']),
                  ('result', '!=', 'skipped'),
                  ]

        last_update = '__last_update'
        builds = request.registry['runbot.build'].search_read(
            request.cr, SUPERUSER_ID,
            domain, ['state', 'result', 'job_age', last_update],
            order='id desc', limit=1)

        if not builds:
            return request.not_found()

        build = builds[0]
        etag = request.httprequest.headers.get('If-None-Match')
        retag = hashlib.md5(build[last_update]).hexdigest()

        if etag == retag:
            return werkzeug.wrappers.Response(status=304)

        if build['state'] == 'testing':
            state = 'testing'
            cache_factor = 1
        else:
            cache_factor = 2
            if build['result'] == 'ok':
                state = 'success'
            elif build['result'] == 'warn':
                state = 'warning'
            else:
                state = 'failed'

        # from https://github.com/badges/shields/blob/master/colorscheme.json
        color = {
            'testing': "#dfb317",
            'success': "#4c1",
            'failed': "#e05d44",
            'warning': "#fe7d37",
        }[state]

        def text_width(s):
            fp = FontProperties(family='DejaVu Sans', size=11)
            w, h, d = TextToPath().get_text_width_height_descent(s, fp, False)
            return int(w + 1)

        class Text(object):
            __slot__ = ['text', 'color', 'width']
            def __init__(self, text, color):
                self.text = text
                self.color = color
                self.width = text_width(text) + 10

        data = {
            'left': Text(branch, '#555'),
            'right': Text(state, color),
        }
        five_minutes = 5 * 60
        headers = [
            ('Content-Type', 'image/svg+xml'),
            ('Cache-Control', 'max-age=%d' % (five_minutes * cache_factor,)),
            ('ETag', retag),
        ]
        return request.render("runbot.badge_" + theme, data, headers=headers)

    @http.route(['/runbot/b/<branch_name>', '/runbot/<model("runbot.repo"):repo>/<branch_name>'], type='http', auth="public", website=True)
    def fast_launch(self, branch_name=False, repo=False, **post):
        pool, cr, uid, context = request.registry, request.cr, request.uid, request.context
        Build = pool['runbot.build']

        domain = [('branch_id.branch_name', '=', branch_name)]

        if repo:
            domain.extend([('branch_id.repo_id', '=', repo.id)])
            order="sequence desc"
        else:
            order = 'repo_id ASC, sequence DESC'

        # Take the 10 lasts builds to find at least 1 running... Else no luck
        builds = Build.search(cr, uid, domain, order=order, limit=10, context=context)

        if builds:
            last_build = False
            for build in Build.browse(cr, uid, builds, context=context):
                if build.state == 'running' or (build.state == 'duplicate' and build.duplicate_id.state == 'running'):
                    last_build = build if build.state == 'running' else build.duplicate_id
                    break

            if not last_build:
                # Find the last build regardless the state to propose a rebuild
                last_build = Build.browse(cr, uid, builds[0], context=context)

            if last_build.state != 'running':
                url = "/runbot/build/%s?ask_rebuild=1" % last_build.id
            else:
                branch = build.branch_id.branch_name
                if branch.startswith('7'):
                    base_url = "http://%s/login?db=%s-all&login=admin&key=admin"
                elif branch.startswith('8'):
                    base_url = "http://%s/login?db=%s-all&login=admin&key=admin&redirect=/web?debug=1"
                else:
                    base_url = "http://%s/web/login?db=%s-all&login=admin&redirect=/web?debug=1"
                url = base_url % (last_build.domain, last_build.dest)
        else:
            return request.not_found()
        return werkzeug.utils.redirect(url)

