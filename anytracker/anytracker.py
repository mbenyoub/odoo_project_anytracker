# coding: utf-8
import re
import logging
from lxml import html
from openerp.osv import fields
from openerp.osv import orm
from tools.translate import _
from lxml import etree
from openerp import SUPERUSER_ID
logger = logging.getLogger(__file__)

ticket_regex = re.compile('([Tt]icket ?#?)([\d]+)')


def add_permalinks(cr, string):
    # replace ticket numbers with permalinks
    if not string:
        return string
    return ticket_regex.subn(
        '<a href="/anytracker/%s/ticket/\\2">\\1\\2</a>' % cr.dbname,
        string)[0]


class Type(orm.Model):
    """ Ticket type (project, ticket, deliverable, etc.)
    """
    _name = 'anytracker.ticket.type'
    _columns = {
        'name': fields.char(u'Title', 255, required=True),
        'code': fields.char(u'Code', 255, required=True),
        'description': fields.text(u'Description'),
        'has_children': fields.boolean(u'Can have children'),
        'default': fields.boolean(u'Default for new tickets'),
        'icon': fields.binary(u'Icon in the kanban'),
    }


class Ticket(orm.Model):

    _name = 'anytracker.ticket'
    _description = "Anytracker tickets"
    _rec_name = 'breadcrumb'
    _order = 'priority ASC, importance DESC, sequence ASC, create_date DESC'  # more logical now
    _parent_store = True
    _inherit = ['mail.thread']

    def _ids_to_be_recalculated(self, cr, uid, ids, context=None):
        """ return list of id which will be recalculated """
        res = []
        for attachment in self.browse(cr, uid, ids):
            if attachment.res_model == 'anytracker.ticket':
                res.append(attachment.res_id)
        return res

    def _has_attachment(self, cr, uid, ids, field_name, args, context=None):
        """ check if tickets have attachment(s) or not"""
        res = {}
        attach_model = self.pool.get('ir.attachment')
        for ticket in ids:
            attachment_ids = attach_model.search(
                cr, uid, [('res_id', '=', ticket), ('res_model', '=', 'anytracker.ticket')])
            if not attachment_ids:
                res[ticket] = False
                continue
            res[ticket] = True
        return res

    def _shortened_description(self, cr, uid, ids, field_name, args, context=None):
        """shortened description used in the list view and kanban view
        """
        res = {}
        limit = 150
        for ticket in self.read(cr, uid, ids, ['id', 'description'], context):
            d = html.fromstring((ticket['description'] or '').strip() or '&nbsp;').text_content()
            res[ticket['id']] = d[:limit] + u'(…)' if len(d) > limit else d
        return res

    def get_breadcrumb(self, cr, uid, ids, under_node_id=0, context=None):
        """Get all the parents up to the root ticket.

        :params under_node_id: if supplied, only the part of the breadcrumbs strictly under
                               this node will be returned.
        """
        res = {}
        for ticket_id in [int(i) for i in ids]:
            cr.execute("WITH RECURSIVE parent(id, parent_id, name) "
                       "AS (SELECT 0, %s, text('') "
                       "    UNION "
                       "    SELECT t.id, t.parent_id, t.name "
                       "    FROM parent p, anytracker_ticket t "
                       "    WHERE t.id = p.parent_id AND t.id != %s) "
                       "SELECT id, parent_id, name FROM parent WHERE id != 0",
                       (ticket_id, under_node_id))

            res[ticket_id] = [dict(zip(('id', 'parent_id', 'name'), line))
                              for line in reversed(cr.fetchall())]
        return res

    def _formatted_breadcrumb(self, cr, uid, ids, field_name, args, context=None):
        """ format the breadcrumb
        TODO : format in the view (in js)
        """
        res = {}
        for i, breadcrumb in self.get_breadcrumb(cr, uid, ids, context=context).items():
            res[i] = u' / '.join([b['name'] for b in breadcrumb])
        return res

    def _formatted_rparent_breadcrumb(self, cr, uid, ids, field_name, args, context=None):
        """A formatted breadcrumbs of parent, relative to context:active_id

        context:active_id is notably available in the Kanban view spawned by Hierarchy action.

        :returns: False for each id if ``active_id`` could not be read from context.
        """
        logger.debug("_formatted_rparent_breadcrumb for %d tickets", len(ids))
        if context is None:
            active_id = None
        else:
            active_id = context.get('active_id')
        if active_id is None:
            return {i: False for i in ids}

        return {i:  u' / '.join(b['name'] for b in bc[:-1])
                for i, bc in self.get_breadcrumb(cr, uid, ids,
                                                 under_node_id=active_id,
                                                 context=context).iteritems()
                }

    def _get_root(self, cr, uid, ticket_id, context=None):
        """Return the real root ticket (not the project_id of the ticket)
        """
        if not ticket_id:
            return False
        ticket = self.read(cr, uid, ticket_id, ['parent_id'], context,
                           load='_classic_write')
        parent_id = ticket.get('parent_id', False)
        if parent_id:
            breadcrumb = self.get_breadcrumb(cr, uid, [parent_id], context)[parent_id]
            if not breadcrumb:
                breadcrumb = [self.read(cr, uid, parent_id, ['name', 'parent_id'])]
            project_id = breadcrumb[0]['id']
        else:
            # if no parent, we are the project
            project_id = ticket_id
        return project_id

    def write(self, cr, uid, ids, values, context=None):
        """write the project_id when writing the parent.
        Also propagate the (in)active flag to the children
        """
        types = self.pool.get('anytracker.ticket.type')
        if not hasattr(ids, '__iter__'):
            ids = [ids]
        children = None
        if 'parent_id' in values:
            root_id = self._get_root(cr, uid, values['parent_id'])
            values['project_id'] = root_id
            for ticket in self.browse(cr, uid, ids, context):
                if ticket.id == values['parent_id']:
                    raise orm.except_orm(_('Error'),
                                         _(u"Think of yourself. Can you be your own parent?"))
                # if reparenting to False, propagate the current ticket as project for children
                project_id = root_id or ticket.id
                # set the project_id of me and all the children
                children = self.search(cr, uid, [('id', 'child_of', ticket.id)])
                super(Ticket, self).write(cr, uid, children, {'project_id': project_id})
                self.recompute_subtickets(cr, uid, values['parent_id'])
        if 'active' in values:
            for ticket_id in ids:
                children = self.search(cr, uid, [
                    ('id', 'child_of', ticket_id),
                    ('active', '=', not values['active'])])
                super(Ticket, self).write(cr, uid, children, {'active': values['active']})

        # replace ticket numbers with permalinks
        if 'description' in values:
            values['description'] = add_permalinks(cr, values['description'])

        # don't allow to set a node as ticket if it has children
        if values.get('type'):
            for ticket in self.browse(cr, uid, ids, context):
                if ticket.child_ids and not types.browse(cr, uid, values.get('type')).has_children:
                    del values['type']

        res = super(Ticket, self).write(cr, uid, ids, values, context=context)
        if 'parent_id' in values:
            for ticket in self.browse(cr, uid, ids, context):
                method_id = (ticket.parent_id.method_id.id
                             if values['parent_id'] is not False else ticket.method_id.id)
                super(Ticket, self).write(cr, uid, children, {'method_id': method_id})
        # correct the parent to be a node
        if 'parent_id' in values:
                type_ids = types.search(cr, uid, [('code', '=', 'node')])
                if type_ids:
                    self.write(cr, uid, values['parent_id'], {'type': type_ids[0]})

        return res

    def _get_permalink(self, cr, uid, ids, field_name, args, context=None):
        base_uri = '/anytracker/%s/ticket/' % cr.dbname
        return dict((r['id'], base_uri + str(r['number']))
                    for r in self.read(cr, uid, ids, ('number',)))

    def create(self, cr, uid, values, context=None):
        """write the project_id when creating
        """
        types = self.pool.get('anytracker.ticket.type')
        type_ids = types.search(cr, uid, [('code', '=', 'node')])
        values.update({
            'number': self.pool.get('ir.sequence').next_by_code(cr, SUPERUSER_ID,
                                                                'anytracker.ticket'),
        })
        if 'parent_id' in values and values['parent_id']:
            project_id = self.read(cr, uid, values['parent_id'],
                                   ['project_id'], load='_classic_write')['project_id']
            values['project_id'] = project_id

        # project creation: auto-assign the 'node' type
        if not values.get('parent_id') and type_ids:
            values['type'] = type_ids[0]

        # replace ticket numbers with permalinks
        if 'description' in values:
            values['description'] = add_permalinks(cr, values['description'])

        ticket_id = super(Ticket, self).create(cr, uid, values, context=context)

        if not values.get('parent_id'):
            self.write(cr, uid, ticket_id, {'project_id': ticket_id})

        # turn the parent into a node
        if 'parent_id' in values and values['parent_id'] and type_ids:
            self.write(cr, uid, values['parent_id'], {'type': type_ids[0]})

        # subscribe project members
        participant_ids = self.browse(cr, uid, ticket_id).project_id.participant_ids
        if participant_ids:
            self.message_subscribe_users(cr, uid, [ticket_id], [p.id for p in participant_ids])

        return ticket_id

    def _default_parent_id(self, cr, uid, context=None):
        """When creating a ticket, return the current ticket as default parent
        or its parent if this is a leaf (to create a sibling)
        """
        active_id = context.get('active_id')
        if not active_id:
            return False
        ticket = self.browse(cr, uid, active_id)
        if not ticket.parent_id:
            return active_id
        elif not ticket.type.has_children:
            return ticket.parent_id.id
        else:
            return active_id

    def _default_type(self, cr, uid, context=None):
        types = self.pool.get('anytracker.ticket.type')
        type_ids = types.search(cr, uid, [('default', '=', True)])
        if not type_ids:
            return False
        return type_ids[0]

    def _subnode_ids(self, cr, uid, ids, field_name, args, context=None):
        """Return the list of children that are themselves nodes."""
        return {i: self.search(cr, uid, [('parent_id', '=', i), ('type.has_children', '=', True)],
                               context=context)
                for i in ids}

    def _nb_children(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for i in ids:
            nb_children = self.search(cr, uid, [('id', 'child_of', i)], count=True)
            res[i] = nb_children
        return res

    def _search_breadcrumb(self, cr, uid, obj, field, domain, context=None):
        """Use the 'name' in the search function for the parent,
        instead of 'breadcrum' which is implicitly used because of the _rec_name
        """
        assert(len(domain) == 1 and len(domain[0]) == 3)  # handle just this case
        (f, o, v) = domain[0]
        return [('name', o, v)]

    def onchange_parent(self, cr, uid, ids, parent_id, context=None):
        """ Fill the method when changing parent
        """
        context = context or {}
        if not parent_id:
            return {}
        method_id = self.read(cr, uid, parent_id, ['method_id'],
                              context, load='_classic_write')['method_id']
        return {'value': {'method_id': method_id}}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form',
                        context=None, toolbar=False, submenu=False):
        """ Allow managers to set an empy parent_id (a project)
        """
        fvg = super(Ticket, self).fields_view_get(
            cr, uid, view_id=view_id, view_type=view_type,
            context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and fvg['type'] == 'form':
            access_obj = self.pool.get('ir.model.access')
            allow = (access_obj.check_groups(cr, uid, "anytracker.group_member")
                     or access_obj.check_groups(cr, uid, "anytracker.group_manager"))
            doc = etree.fromstring(fvg['arch'])
            try:
                node = doc.xpath("//field[@name='parent_id']")[0]
            except:
                logger.error("It seems you're using a broken version of OpenERP")
                return fvg
            orm.transfer_modifiers_to_node({'required': not allow}, node)
            fvg['arch'] = etree.tostring(doc)
        return fvg

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        """
            Overwrite the name_search function to search a ticket
            with their name or thier number
        """
        if not args:
            args = []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            ticket_ids = []
            if name.isdigit():
                number = int(name)
                ticket_ids = self.search(cr, uid, [('number', '=', number)] + args,
                                         limit=limit, context=context)
            else:
                ticket_ids = self.search(cr, uid, [('name', operator, name)] + args,
                                         limit=limit, context=context)
            if len(ticket_ids) > 0:
                return self.name_get(cr, uid, ticket_ids, context)
        return super(Ticket, self).name_search(cr, uid, name, args, operator=operator,
                                               context=context, limit=limit)

    def trash(self, cr, uid, ids, context=None):
        """ Trash the ticket
        set active = False, and move to the last stage
        """
        if not hasattr(ids, '__iter__'):
            ids = [ids]
        self.write(cr, uid, ids, {
            'active': False,
            'state': 'trashed',
            'progress': 100.0,
            'stage_id': False})
        self.recompute_parents(cr, uid, ids)

    def reactivate(self, cr, uid, ids, context=None):
        """ reactivate a trashed ticket
        """
        if not hasattr(ids, '__iter__'):
            ids = [ids]
        self.write(cr, uid, ids, {'active': True, 'state': 'running'})
        stages = self.pool.get('anytracker.stage')
        for ticket in self.browse(cr, uid, ids):
            start_ids = stages.search(cr, uid, [('method_id', '=', ticket.method_id.id),
                                                ('progress', '=', 0)])
            if len(start_ids) != 1:
                raise orm.except_orm(_('Configuration error !'),
                                     _('One and only one stage should have a 0% progress'))
            # write stage in a separate line to let it recompute progress and risk
            ticket.write({'stage_id': start_ids[0]})
        self.recompute_parents(cr, uid, ids)

    def cron(self, cr, uid, context=None):
        """Anytracker CRON tasks
        To be overloaded by submodules
        """
        return

    _columns = {
        'name': fields.char('Title', 255, required=True),
        'number': fields.integer('Number'),
        'type': fields.many2one(
            'anytracker.ticket.type',
            'Type',
            required=True,
            select=True),
        'permalink': fields.function(_get_permalink, type='string', string='Permalink',
                                     obj='anytracker.ticket', method=True),
        'description': fields.text('Description', required=False),
        'create_date': fields.datetime('Creation Time'),
        'write_date': fields.datetime('Modification Time'),
        'subnode_ids': fields.function(_subnode_ids,
                                       type='one2many',
                                       relation='anytracker.ticket',
                                       method=True,
                                       readonly=True,
                                       string='Sub-nodes'),
        'shortened_description': fields.function(
            _shortened_description,
            type='text',
            obj='anytracker.ticket',
            string='Description'),
        'breadcrumb': fields.function(
            _formatted_breadcrumb,
            fnct_search=_search_breadcrumb,
            type='char',
            obj='anytracker.ticket',
            string='Location'),
        'relative_parent_breadcrumbs': fields.function(
            _formatted_rparent_breadcrumb,
            type='char',
            obj='anytracker.ticket',
            string='Location'),
        'duration': fields.selection(
            [(0, '< half a day'), (None, 'Will be computed'), (1, 'Half a day')],
            'duration'),
        'child_ids': fields.one2many(
            'anytracker.ticket',
            'parent_id',
            'Sub-tickets',
            required=False),
        'nb_children': fields.function(
            _nb_children,
            method=True,
            string='# of children',
            type='integer',
            help='Number of children'),
        'participant_ids': fields.many2many(
            'res.users',
            'anytracker_ticket_assignment_rel',
            'ticket_id',
            'user_id',
            required=False),
        'parent_id': fields.many2one(
            'anytracker.ticket',
            'Parent',
            required=False,
            select=True,
            ondelete='cascade'),
        'project_id': fields.many2one(
            'anytracker.ticket',
            'Project',
            ondelete='cascade',
            domain=[('parent_id', '=', False)],
            readonly=True),
        'requester_id': fields.many2one(
            'res.users',
            'Requester'),
        'parent_left': fields.integer('Parent Left', select=1),
        'parent_right': fields.integer('Parent Right', select=1),
        'sequence': fields.integer('sequence'),
        'active': fields.boolean('Active', help=("Uncheck to make the project disappear, "
                                                 "instead of deleting it")),
        'state': fields.selection(
            [('running', 'Running'),
             ('trashed', 'Trashed')],
            'State',
            required=True),
        'icon': fields.related('type', 'icon', type='binary'),
        'has_attachment': fields.function(
            _has_attachment,
            type='boolean',
            obj='anytracker.ticket',
            string='Has attachment ?',
            store={'ir.attachment': (_ids_to_be_recalculated, ['res_id', 'res_model'], 10)})
    }

    _defaults = {
        'type': _default_type,
        'duration': 0,
        'parent_id': _default_parent_id,
        'active': True,
        'state': 'running',
    }

    _sql_constraints = [('number_uniq', 'unique(number)', 'Number must be unique!')]


class ResPartner(orm.Model):
    """ Improve security
    """
    _inherit = 'res.partner'

    def _anytracker_search_users(self, cr, uid, obj, field, domain, context=None):
        assert(len(domain) == 1 and domain[0][0] == 'anytracker_user_ids')
        user_id = domain[0][2]
        cr.execute('select distinct u.partner_id from res_users u, '
                   'anytracker_ticket_assignment_rel m, anytracker_ticket_assignment_rel n '
                   'where m.user_id=%s and u.id=n.user_id and n.ticket_id=m.ticket_id;',
                   (user_id,))
        return [('id', domain[0][1], tuple(a[0] for a in cr.fetchall()))]

    _columns = {
        'anytracker_user_ids': fields.function(
            None,
            fnct_search=_anytracker_search_users,
            type='one2many',
            string='Allowed users',
            obj='res.users',
            method=True),
    }


class MailMessage(orm.Model):
    _inherit = 'mail.message'

    def create(self, cr, uid, values, context=None):
        if values.get('model') == 'anytracker.ticket' and 'body' in values:
            values['body'] = add_permalinks(cr, values['body'])
        return super(MailMessage, self).create(cr, uid, values, context)
