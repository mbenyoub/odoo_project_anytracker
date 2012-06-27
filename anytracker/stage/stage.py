# coding: utf-8
from osv import fields, osv
from tools.translate import _


class stage(osv.osv):
    """Stage of a ticket.
    Correspond to kanban columns
    """
    _name = 'anytracker.stage'
    _order = 'sequence'
    _columns = {
        'name': fields.char('name', size=64, required=True),
        'state': fields.char('state', size=64, required=True),
        'method_id': fields.many2one('anytracker.method', _('Project method')),
        'sequence': fields.integer('Sequence', help='Sequence'),
    }


class Ticket(osv.osv):

    _inherit = 'anytracker.ticket'

    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        """return stage names for the group_by_full directive
        """
        # XXX improve the filter to handle categories
        stage_osv = self.pool.get('anytracker.stage')
        project_id = context.get('own_values', None)
        if not project_id:
            return []
        project_id = project_id['self']
        ticket_osv = self.pool.get('anytracker.ticket')
        method = ticket_osv.browse(cr, uid, project_id, context).method_id
        if not method:
            return []
        stage_ids = stage_osv.search(cr, uid, [('method_id','=',method.id)], context=context)
        stage_names = stage_osv.name_get(cr, access_rights_uid, stage_ids, context=context)
        return stage_names

    def _set_stage(self, cr, uid, ids, stage_id, context):
        """set the stage of a ticket.
        For a node, it should set all children as well
        """
        for ticket in self.browse(cr, uid, ids, context):
            self._set_stage(cr, uid, [i.id for i in ticket.child_ids], stage_id, context)
            self.write(cr, uid, ticket.id, {'stage_id': stage_id}, context)

    def stage_previous(self, cr, uid, ids, context=None):
        """move the ticket to the previous stage
        """
        stage_pool = self.pool.get('anytracker.stage')
        for ticket in self.browse(cr, uid, ids, context):
            stage_id = ticket.stage_id.id
            method = ticket.project_id.method_id
            if not method:
                raise osv.except_osv(_('Warning !'),_('No method defined in the project.'))
            stage_ids = stage_pool.search(cr, uid, [('method_id','=',method.id)])
            if stage_id == stage_ids[0]: # first stage
                next_stage = False
            elif stage_id not in stage_ids: # no stage
                continue
            else:
                next_stage = stage_ids[stage_ids.index(stage_id)-1]
            self._set_stage(cr, uid, [ticket.id], next_stage, context)

    def stage_next(self, cr, uid, ids, context=None):
        """move the ticket to the next stage
        """
        stage_pool = self.pool.get('anytracker.stage')
        for ticket in self.browse(cr, uid, ids, context):
            stage_id = ticket.stage_id.id
            method = ticket.project_id.method_id
            if not method:
                raise osv.except_osv(_('Warning !'),_('No method defined in the project.'))
            stage_ids = stage_pool.search(cr, uid, [('method_id','=',method.id)])
            if stage_id == stage_ids[-1]: # last stage
                raise osv.except_osv(_('Warning !'),_("You're already in the last stage"))
            elif stage_id not in stage_ids: # no stage
                next_stage = stage_ids[0]
            else:
                next_stage = stage_ids[stage_ids.index(stage_id)+1]
            self._set_stage(cr, uid, [ticket.id], next_stage, context)

    def write(self, cr, uid, ids, values, context=None):
        """set children stages when writing stage_id
        """
        res = super(Ticket, self).write(cr, uid, ids, values, context=context)
        stage_id = values.get('stage_id')
        if stage_id:
            if not hasattr(ids, '__iter__'): ids = [ids]
            for ticket in self.browse(cr, uid, ids, context):
                self._set_stage(cr, uid, [i.id for i in ticket.child_ids], stage_id, context)
        return res

    _columns = {
        'stage_id': fields.many2one('anytracker.stage',
                                    ('Stage'),
                                    domain="[('method_id','=',project_method_id)]")
    }

    _group_by_full = {
        'stage_id': _read_group_stage_ids
    }

