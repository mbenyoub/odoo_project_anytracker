# coding: utf-8
from osv import fields, osv
from tools.translate import _
import time

class ticket(osv.osv):

    _name = 'anytracker.ticket'
    _description = "Tickets for project management"

    def _get_siblings(self, cr, uid, ids, field_name, args, context=None):
        """ get tickets at the same hierachical level
        """
        res = {}
        for ticket in self.browse(cr, uid, ids, context):
            domain = [
                ('parent_id', '=', ticket.parent_id.id),  # the same parent
                ('id', '!=', ticket.id),  # not me
            ]
            res[ticket.id] = self.search(cr, uid, domain, context=context)
        return res

    def _shorten_description(self, cr, uid, ids, field_name, args, context=None):
        """shortened description for the kanban
        """
        res = {}
        for ticket in self.browse(cr, uid, ids, context):
            res[ticket.id] = ticket.description and ticket.description[:250] + '...' or False
        return res

    def _breadcrumb(self, cr, uid, ids, field_name, args, context=None):
        """ get all the parents until the root ticket
        """
        res = {}
        for ticket in self.browse(cr, uid, ids, context):
            breadcrumb = []
            current_ticket = ticket
            while current_ticket.parent_id:
                breadcrumb.insert(0, current_ticket.parent_id.name)
                current_ticket = current_ticket.parent_id
            res[ticket.id] = u' → '.join(breadcrumb)
        return res

    _columns = {
        'name': fields.char('Name', 255, required=True),
        'description': fields.text('Description', required=False),
        'shortened_description': fields.function(_shorten_description, type='text', obj='anytracker.ticket', string='Description'),
        'breadcrumb': fields.function(_breadcrumb, type='text', obj='anytracker.ticket', string='Description'),
        'siblings_ids': fields.function(_get_siblings, type='many2many', obj='anytracker.ticket', string='Siblings', method=True),
        'duration': fields.selection([(0, '< half a day'), (None, 'Will be computed'), (1, 'Half a day')], 'duration'),
        'child_ids': fields.one2many('anytracker.ticket', 'parent_id', 'Children', required=False),
        'assignedto_ids': fields.many2many('res.users', 'ticket_assignement_rel', 'ticket_id', 'user_id', required=False),
        'parent_id': fields.many2one('anytracker.ticket', 'Parent', required=False),
        'requester_id': fields.many2one('res.users', 'Requester'),
        'id_mindmap': fields.char('ID MindMap', size=64),
        'created_mindmap': fields.datetime('Created MindMap'),
        'modified_mindmap': fields.datetime('Modified MindMap'),
        'modified_openerp': fields.datetime('Modified OpenERP'),
    }

    _defaults = {
        'duration': 0,
    }


    def makeTreeData(self, cr, uid, ids, context=None):
        '''Return all ticket of a tree so ordered'''
        DATA_TO_RETRIEVE = ['description', 'modified_mindmap', 'child_ids', 'rating_ids', 'id_mindmap', 'modified_openerp', 'created_mindmap', 'id', 'name']
        def makeRecursTree(ticket_branch):
            ticket_ids = self.search(cr, uid, [('parent_id','=', ticket_branch['id'])])
            for ticket_id in ticket_ids:
                if not ticket_branch.has_key('child'):
                    ticket_branch['child'] = []
                ticket_branch['child'].append(self.read(cr, uid, ticket_id, DATA_TO_RETRIEVE, context))
                makeRecursTree(ticket_branch['child'][len(ticket_branch['child'])-1])
        ticket_tree = []
        for ticket_tree_data in self.read(cr, uid, ids, DATA_TO_RETRIEVE, context):
            ticket_tree.append(ticket_tree_data)
            ticket_tree_data = makeRecursTree(ticket_tree_data)
        return ticket_tree

