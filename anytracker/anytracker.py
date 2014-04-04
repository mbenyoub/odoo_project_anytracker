# coding: utf-8
import logging
from osv import fields, osv
from tools.translate import _
from lxml import etree
from openerp.osv.orm import transfer_modifiers_to_node
logger = logging.getLogger(__file__)


class Ticket(osv.Model):

    _name = 'anytracker.ticket'
    _description = "Anytracker tickets"
    _rec_name = 'breadcrumb'
    _order = 'priority ASC, importance DESC, sequence ASC, create_date DESC'  # more logical now
    _parent_store = True
    _inherit = ['mail.thread']

    def _shortened_description(self, cr, uid, ids, field_name, args, context=None):
        """shortened description used in the list view and kanban view
        """
        res = {}
        limit = 150
        for ticket in self.read(cr, uid, ids, ['id', 'description'], context):
            descr = ticket['description'] or ''
            res[ticket['id']] = descr[:limit] + u'(…)' if len(descr) > limit else descr
        return res

    def _kanban_description(self, cr, uid, ids, field_name, args, context=None):
        """shortened description when hovering a ticket in the kanban
        """
        res = {}
        for ticket in self.read(cr, uid, ids, ['id', 'description'], context):
            lines = (ticket['description'] or '').splitlines()
            if len(lines) > 5:
                lines = lines[:5]
                lines.append(u'(…)')
            res[ticket['id']] = '<br/>'.join(lines)
        return res

    def get_breadcrumb(self, cr, uid, ids, context=None):
        """ get all the parents up to the root ticket
        """
        res = {}
        for ticket_id in [int(i) for i in ids]:
            cr.execute("WITH RECURSIVE parent(id, parent_id, name) as "
                       "(select 0, %s, text('') UNION SELECT t.id, t.parent_id, t.name "
                       " FROM parent p, anytracker_ticket t WHERE t.id=p.parent_id) "
                       "SELECT id, parent_id, name FROM parent WHERE id!=0", (ticket_id,))

            # The same using parent_store. Actually slower for our typical trees:
            # cr.execute("select b.id, b.parent_id, b.name "
            #           "from anytracker_ticket a join anytracker_ticket b "
            #           "on a.parent_left >= b.parent_left and a.parent_right<=b.parent_right "
            #           "and a.id=%s order by b.parent_left", (ticket_id,))
            res[ticket_id] = [dict(zip(('id', 'parent_id', 'name'), line))
                              for line in reversed(cr.fetchall())]
        return res

    def _formatted_breadcrumb(self, cr, uid, ids, field_name, args, context=None):
        """ format the breadcrumb
        TODO : format in the view (in js)
        """
        res = {}
        for i, breadcrumb in self.get_breadcrumb(cr, uid, ids, context).items():
            res[i] = u' / '.join([b['name'] for b in breadcrumb])
        return res

    def _get_admin_id(self, cr, uid, context=None):
        xml_obj = self.pool.get('ir.model.data')
        res_users = self.pool.get('res.users')
        admin_group_id = xml_obj.get_object_reference(cr, uid, 'base', 'group_erp_manager')[1]
        domain = [
            ('groups_id', "in", [admin_group_id]),
        ]
        admin_ids = res_users.search(cr, uid, domain, context=context)
        if admin_ids:
            return admin_ids[0]
        raise osv.except_osv(_('Error'), _('No user with ERP Manager group found'))

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
        if not hasattr(ids, '__iter__'):
            ids = [ids]
        children = None
        if 'parent_id' in values:
            root_id = self._get_root(cr, uid, values['parent_id'])
            values['project_id'] = root_id
            for ticket_id in ids:
                if ticket_id == values['parent_id']:
                    raise osv.except_osv(_('Error'),
                                         _(u"Think of yourself. Can you be your own parent?"))
                # reparenting to False, set current ticket as project for children
                project_id = root_id or ticket_id
                # set the project_id of me and all the children
                children = self.search(cr, uid, [('id', 'child_of', ticket_id)])
                self.write(cr, uid, children, {'project_id': project_id})
        if 'active' in values:
            for ticket_id in ids:
                children = self.search(cr, uid, [
                    ('id', 'child_of', ticket_id),
                    ('active', '=', not values['active'])])
                super(Ticket, self).write(cr, uid, children, {'active': values['active']})
        res = super(Ticket, self).write(cr, uid, ids, values, context=context)
        return res

    def _get_permalink(self, cr, uid, ids, field_name, args, context=None):
        base_uri = '/anytracker/%s/ticket/' % cr.dbname
        return dict((r['id'], base_uri + str(r['number']))
                    for r in self.read(cr, uid, ids, ('number',)))

    def create(self, cr, uid, values, context=None):
        """write the project_id when creating
        """
        values.update({
            'number': self.pool.get('ir.sequence').next_by_code(cr, self._get_admin_id(cr, uid),
                                                                'anytracker.ticket'),
        })
        ticket_id = super(Ticket, self).create(cr, uid, values, context=context)
        # set the project of the ticket
        root_id = self._get_root(cr, uid, ticket_id)
        self.write(cr, uid, ticket_id, {'project_id': root_id})
        return ticket_id

    def _default_parent_id(self, cr, uid, context=None):
        """Return the current ticket of the parent if this is a leaf
        """
        ticket_obj = self.pool.get('anytracker.ticket')
        active_id = context.get('active_id')
        if not active_id:
            return False
        ticket = ticket_obj.browse(cr, uid, active_id)
        if not ticket.parent_id:
            return active_id
        elif not ticket.child_ids:
            return ticket.parent_id.id
        else:
            return active_id

    def _default_project_id(self, cr, uid, context=None):
        """Return the same project as the active_id
        """
        ticket_obj = self.pool.get('anytracker.ticket')
        active_id = context.get('active_id')
        if not active_id:
            return False
        ticket = ticket_obj.browse(cr, uid, active_id)
        if not ticket.parent_id:
            return active_id
        else:
            return ticket.project_id.id

    def _subnode_ids(self, cr, uid, ids, field_name, args, context=None):
        """Return the list of children that are themselves nodes."""
        ticket_obj = self.pool.get('anytracker.ticket')
        # GR: I suppose we don't use self directly because it may be overridden ?
        return {i: ticket_obj.search(cr, uid, [('parent_id', '=', i), ('child_ids', '!=', False)],
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
            allow = access_obj.check_groups(cr, uid, "anytracker.group_manager")
            doc = etree.fromstring(fvg['arch'])
            try:
                node = doc.xpath("//field[@name='parent_id']")[0]
            except:
                logger.error("It seems you're using a broken version of OpenERP")
                return fvg
            transfer_modifiers_to_node({'required': not allow}, node)
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

    _columns = {
        'name': fields.char('Title', 255, required=True),
        'number': fields.integer('Number'),
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
        'kanban_description': fields.function(
            _kanban_description,
            type='text',
            obj='anytracker.ticket',
            string='Description'),
        'breadcrumb': fields.function(
            _formatted_breadcrumb,
            fnct_search=_search_breadcrumb,
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
            store=False, help='Number of children'),
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
    }

    _defaults = {
        'duration': 0,
        'parent_id': _default_parent_id,
        'project_id': _default_project_id,
        'active': True,

    }

    _sql_constraints = [('number_uniq', 'unique(number)', 'Number must be unique!')]
