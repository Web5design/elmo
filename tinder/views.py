# Create your views here.
from django.db.models import Q
from django.shortcuts import render_to_response
from django.template import Context, loader
from django.http import HttpResponse, HttpResponseNotFound
from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.contrib.syndication.views import feed
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

import operator
from bz2 import BZ2File
import os
import re
from datetime import datetime, timedelta
import calendar
from mbdb.models import *
from tinder.models import MasterMap


resultclasses = ['success', 'warning', 'failure', 'skip', 'except']

def debug_(*msg):
    if False:
        print ' '.join(msg)


class BColumn(object):
    '''Builder column

    Helper object to keep track of the parallel build columns per
    builder.

    '''

    def __init__(self, name):
        self.name = name
        self.cols = []

    def addRow(self):
        for c in self.cols:
            c[0]['rowspan'] += 1
        if not self.cols:
            self.cols.append([{'class': 'white',
                               'obj': None,
                               'rowspan': 1}])

    def changeCell(self, open_or_close, class_, obj):
        debug_("%s received %s" % (self.name, open_or_close))
        if open_or_close == 'close':
            cell = {'class': class_,
                    'obj': obj,
                    'rowspan': 1}
            if not self.cols:
                # we didn't even start yet, just add this as first inner col
                self.cols.append([cell])
                return
            # try to find a free column
            hasEmptyCol = False
            for i in xrange(len(self.cols)):
                if self.cols[i][0]['class'] == 'white':
                    # found the right column
                    hasEmptyCol = True
                    break
            if not hasEmptyCol:
                # we don't have an free column, add a new one
                # first, fill it up with an empty cell
                oldrows = sum(map(lambda c: c['rowspan'], self.cols[0]))
                self.cols.append([{'class': 'white',
                               'obj': None,
                               'rowspan': oldrows}])
                i = len(self.cols) - 1
            # add cell, increase rowspan of all others
            for j in xrange(len(self.cols)):
                if j == i:
                    c = self.cols[j]
                    # if the first cell has no rowspan, just replace it
                    if c[0]['rowspan'] == 0:
                        c[0] = cell
                    else:
                        c.insert(0, cell)
                else:
                    self.cols[j][0]['rowspan'] += 1
        else:
            # open_or_close == 'open'
            cell = {'class': 'white',
                    'obj': None,
                    'rowspan': 0}
            for c in self.cols:
                if c[0]['obj'] == obj:
                    c.insert(0, cell)
                    return
            debug_('there should be a cell to close here', self.name, str(obj))

    def finish(self):
        '''Finish this builder column.

        Pops leading empyt cells.

        '''
        for c in self.cols:
            if c[0]['rowspan'] == 0:
                c.pop(0)

    def rows(self):
        '''Iterator over all rows, returning a list of cells.'''

        # Can't hurt to finish ourselves
        self.finish()
        if not any(self.cols):
            # no content
            return
        spans = [0] * len(self.cols)
        while any(self.cols) or any(spans):
            r = []
            for i in xrange(len(self.cols)):
                if spans[i] == 0:
                    if self.cols[i]:
                        c = self.cols[i].pop()
                        spans[i] = c['rowspan'] - 1
                        if i == 0:
                            c['class'] += ' left'
                        if i == len(self.cols) - 1:
                            c['class'] += ' right'
                        r.append(c)
                else:
                    spans[i] -= 1
            yield r

    @property
    def width(self):
        return len(self.cols)

    def lengths(self):
        l = []
        for col in self.cols:
            ll = 0
            for cell in col:
                ll += cell['rowspan']
            l.append(ll)
        return l

def _waterfall(request):
    '''Inner helper for waterfall display. This method is factored out
    of waterfall for testing purposes.

    '''
    try:
        end_t = max(Build.objects.order_by('-pk')[0].starttime,
                    Change.objects.order_by('-pk')[0].when)
        start_t = end_t - timedelta(1)/2
    except IndexError:
        # wallpaper against an empty build database
        end_t = datetime.max
        start_t = datetime.min
    buildf = {}
    props = []
    isEnd = True
    filters = None
    if request is not None:
        if 'endtime' in request.GET:
            try:
                end_t = datetime.utcfromtimestamp(int(request.GET['endtime']))
            except Exception:
                pass
            isEnd = False
        if 'starttime' in request.GET:
            try:
                start_t = datetime.utcfromtimestamp(int(request.GET['starttime']))
            except Exception:
                pass
        if 'hours' in request.GET:
            try:
                td = timedelta(1)/24*int(request.GET['hours'])
                if 'starttime' in request.GET and 'endtime' not in request.GET:
                    end_t = start_t + td
                    isEnd = False
                else:
                    start_t = end_t - td
            except Exception:
                pass
        timeopts = ['endtime', 'starttime', 'hours']
        filters = request.GET.copy()
        for opt in timeopts:
            if opt in filters:
                filters.pop(opt)
        builderopts = ['name', 'category']
        buildopts = ['slavename']
        for k, v in request.GET.items():
            if k in timeopts:
                continue
            if k in builderopts:
                buildf[str('builder__' + k)] = v
            elif k in buildopts:
                buildf[str(k)] = v
            else:
                props.append(Property.objects.filter(name=k).filter(value=v))

    # get the real hours, for consecutive queries
    time_d = end_t - start_t
    hours = int(round(time_d.seconds/3600.0))
    if time_d.days:
        hours += time_d.days * 24

    q_buildsdone = Build.objects.filter(Q(endtime__gt = start_t) | 
                                        Q(endtime__isnull = True),
                                        Q(starttime__lte = end_t))
    if buildf:
        q_buildsdone = q_buildsdone.filter(**buildf)
    for p in  props:
        q_buildsdone = q_buildsdone.filter(properties__in = p)
    debug_("found %d builds" % q_buildsdone.count())
    q_changes = Change.objects.filter(when__gt = start_t,
                                      when__lte = end_t)
    def ievents(builds, changes):
        starts = []
        c_iter = changes.order_by('-when', '-pk').iterator()
        try:
            c = c_iter.next()
        except StopIteration:
            c = None
        # yield an end change event if we have changes first
        if c:
            yield(None, 'end change', c)
        # yield end-events for running builds
        for b in builds.filter(endtime__isnull=True).order_by('-starttime', '-pk'):
            starts.insert(0, b)
            yield (None, 'end started build', b)
        # restrict to only finished builds now
        builds = builds.filter(endtime__isnull=False)
        b_iter = builds.order_by('-endtime', '-pk').iterator()
        try:
            e = b_iter.next()
        except StopIteration:
            e = None
        b = None
        if starts:
            b = starts.pop()
        while e or b or c:
            if (e is not None and 
                (b is None or e.endtime >= b.starttime) and 
                (c is None or e.endtime >= c.when)):
                yield (e.endtime, 'end build', e)
                starts.insert(0, e)
                if b is not None:
                    starts.append(b)
                starts.sort(lambda r,l: cmp(r.starttime, l.starttime))
                b = starts.pop()
                try:
                    e = b_iter.next()
                except StopIteration:
                    e = None
                continue
            if (b is not None and
                (e is None or b.starttime > e.endtime) and
                (c is None or b.starttime > c.when)):
                yield (b.starttime, 'begin build', b)
                if starts:
                    b = starts.pop()
                else:
                    b = None
                continue
            assert c
            yield (c.when, 'start change', c)
            try:
                c = c_iter.next()
            except StopIteration:
                c = None
            if c:
                # we have more changes, open up the next cell
                yield(None, 'end change', c)

    builders = list(q_buildsdone.values_list('builder__name',
                                             flat=True).distinct().order_by('builder__name'))
    cols = dict((builder, BColumn(builder)) for builder in builders)
    blame = BColumn('blame')
    for t, type_, obj in ievents(q_buildsdone, q_changes):
        debug_(type_)
        if isinstance(obj, Build):
            debug_(str(obj.buildnumber))
        if type_.endswith('change'):
            if type_.startswith('end'):
                open_or_close = 'close'
            else:
                open_or_close = 'open'
            blame.changeCell(open_or_close, 'white', obj)
            if open_or_close == 'open':
                for bcol in cols.itervalues():
                    bcol.addRow()
        else:
            # build
            class_ = type_.split(' ', 1)[1]
            if obj.result is not None:
                class_ += ' ' + resultclasses[obj.result]
            builder = obj.builder.name
            if type_.startswith('end'):
                open_or_close = 'close'
            else:
                open_or_close = 'open'
            if open_or_close == 'close':
                blame.addRow()
            for bname, bcol in cols.iteritems():
                if bname == builder:
                    bcol.changeCell(open_or_close, class_, obj)
                elif open_or_close == 'close':
                    bcol.addRow()

    blame.finish()
    for bcol in cols.values():
        bcol.finish()

    if filters:
        filters = filters.urlencode() + '&'
    else:
        filters = ''
    def timestamp(dto):
        return "%d" % calendar.timegm(dto.utctimetuple())
    hourlist = [12, 24]
    if hours in hourlist:
        hourlist.remove(hours)
    hourlist.insert(0, hours)
    return blame, cols, filters, {'start': timestamp(start_t),
                                  'end': timestamp(end_t),
                                  'start_t': start_t,
                                  'end_t': end_t,
                                  'hourlist': hourlist,
                                  'hours': hours, 'isEnd': isEnd}

def waterfall(request):
    '''Waterfall view

    Main worker is _waterfall, this one just forwards the results
    to the template.

    '''
    blame, buildercolumns, filters, times = _waterfall(request)
    builders = [blame] + [buildercolumns[k]
                          for k in sorted(buildercolumns.keys())]
    head = [{'name': b.name, 'span': b.width}
            for b in builders]
    rows = []
    rows = [reduce(operator.add, t, [])
            for t in zip(*map(lambda b: b.rows(), builders))]
    return render_to_response('tinder/waterfall.html', 
                              {'times': times, 'filters': filters,
                               'heads': head,
                               'rows': rows})

def builds_for_change(request):
    """View for builds for one particular change.

    Has a corresponding feed in BuildsForChangeFeed.
    """
    try:
        changenumber = int(request.GET['change'])
        change = Change.objects.get(number = changenumber)
    except (ValueError, KeyError):
        return HttpResponseNotFound("Given change does not exist")

    builds = Build.objects.filter(sourcestamp__changes=change).order_by('starttime')
    pending = BuildRequest.objects.filter(builds__isnull=True,
                                          sourcestamp__changes=change).count()
    running = []
    done = []
    for b in builds:
        done.append({'build': b,
                     'class': (b.result is not None and resultclasses[b.result])
                     or ''})

    try:
        from life.models import Push
        url = str(Push.objects.get(changesets__revision=change.revision,
                                   changesets__repository__name=change.branch))
    except:
        url=None
    
    return render_to_response('tinder/builds_for.html',
                              {'done_builds': done,
                               'pending': pending,
                               'url': url,
                               'change': change})


class BuildsForChangeFeed(Feed):
    ttl = str(5*60)
    title_template = 'tinder/builds_for_change_title.html'

    def get_object(self, bits):
        """Return a closure to be used to create the feed for this change.

        404 for anything that isn't a single change ID.
        """
        if len(bits) != 1:
            raise ObjectDoesNotExist
        try:
            id = int(bits[0])
        except ValueError:
            raise ObjectDoesNotExist
        return Change.objects.get(number=id)

    def title(self, change):
        title = []
        pending = BuildRequest.objects.filter(builds__isnull=True,
                                              sourcestamp__changes=change).count()
        if pending:
            title.append("%d pending" % pending)
        builds = Build.objects.filter(sourcestamp__changes=change)
        building = builds.filter(endtime__isnull=True).count()
        if building:
            title.append("%d building" % building)
        failed = builds.filter(result=2).count()
        if failed:
            title.append("%d failed" % failed)
        warnings = builds.filter(result=1).count()
        if warnings:
            title.append("%d warnings" % warnings)
        good = builds.filter(result=0).count()
        if good:
            title.append("%d good" % good)
        if not title:
            title.append("no builds")
        return ", ".join(title)

    def link(self, change):
        lnk = reverse('tinder.views.builds_for_change') + '?change=%d' % change.pk
        lnk = self.request.build_absolute_uri(lnk)
        return lnk

    def description(self, change):
        tmpl = '''Builds for %s by %s'''
        return tmpl % (change.comments, change.who)

    def items(self, change):
        builds = Build.objects.filter(sourcestamp__changes=change)
        return builds.order_by('starttime')

    def item_link(self, build):
        lnk = reverse('tinder_show_build',
                      args=(build.builder.name, build.buildnumber))
        lnk = self.request.build_absolute_uri(lnk)
        return lnk

def showbuild(request, buildername, buildnumber):
    try:
        builder = Builder.objects.get(name=buildername)
    except Builder.DoesNotExist:
        return HttpResponseNotFound("No such Builder")
    try:
        buildnumber = int(buildnumber)
        build = builder.builds.get(buildnumber=buildnumber)
    except (ValueError, Build.DoesNotExist):
        return HttpResonseNotFound("No such build")

    steps = build.steps.order_by('pk')
    props = build.propertiesAsList()

    return render_to_response('tinder/showbuild.html',
                              {'build': build,
                               'steps': steps,
                               'props': props})

mastermaps = MasterMap.objects.filter(webhead__name='head 1')
def generateLog(master, filename):
    """Generic generator to read buildbot step logs.
    """
    base = mastermaps.get(master__name=master).logmount
    head=re.compile('(\d+):(\d)')
    f = None
    filename = os.path.join(base, filename)
    try:
        f = BZ2File(filename + ".bz2", "r")
    except IOError:
        f = open(filename, "r")
    buflen = 64*1024
    buf = f.read(buflen)
    offset = 0
    while buf:
        m = head.match(buf, offset)
        if m:
            cnt = int(m.group(1))
            channel = int(m.group(2))
            offset = m.end()
            chunk = buf[offset:offset+cnt-1]
            if len(chunk) < cnt - 1:
                cnt -= len(chunk)
                morebuf = f.read(cnt)
                chunk += morebuf[:-1] # drop ','
                buf = []
                offset = 0
            else:
                offset += cnt
            yield {'channel': channel, 'data': chunk}
        buf = buf[offset:] + f.read(buflen)
        offset = 0

def showlog(request, master, file):
    """Show a log file.

    Right now, this only supports locally mounted buildbot logs.
    """
    def classify(chunks):
        classes = ["stdout", "stderr", "header"]
        for chunk in chunks:
            if chunk['channel'] < 3:
                yield {'class': classes[chunk['channel']],
                       'data': chunk['data']}
    build = Build.objects.get(steps__logs__filename=file,
                              builder__master__name=master)
    return render_to_response('tinder/log.html',
                              {'build': build,
                               'file': file,
                               'chunks': classify(generateLog(master, file))})
