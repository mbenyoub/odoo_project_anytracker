# coding: utf-8
from openerp.osv import osv
from openerp.osv import fields
from tools.translate import _


class Stage(osv.Model):
    """Stage of a ticket.
    Correspond to kanban columns
    """
    _name = 'anytracker.stage'
    _order = 'sequence'
    _columns = {
        'name': fields.char('name', size=64, required=True, translate=True),
        'description': fields.text('Description', translate=True),
        'state': fields.char('state', size=64, required=True),
        'method_id': fields.many2one('anytracker.method', 'Project method',
                                     required=True, ondelete='cascade'),
        'sequence': fields.integer('Sequence', help='Sequence'),
        'force_rating': fields.boolean(
            'Force rating', help='Forbid entering this stage without a rating on the ticket'),
        'forbidden_complexity_ids': fields.many2many(
            'anytracker.complexity',
            'anytracker_stage_forbidden_complexities',
            'stage_id', 'complexity_id',
            'Forbidden complexities', help='complexities forbidden for this stage'),
        'progress': fields.float(
            'Progress', help='Progress value of the ticket reaching this stage'),
        'groups_allowed': fields.many2many('res.groups',
                                           'anytracker_stage_res_groups_rel',
                                           'res_group_id',
                                           'anytracker_stage_id',
                                           'Authorized groups to move ticket to this stage'),
    }

    _defaults = {'groups_allowed': False}


class Ticket(osv.Model):
    """ Add stage and progress functionality to tickets
    Progress is based on stages. Each stage has a progress,
    and the progress is copied on the ticket
    """

    _inherit = 'anytracker.ticket'

    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None,
                              access_rights_uid=None, context=None):
        """return all stage names for the group_by directive, so that the kanban
        has all columns even if there is no ticket in a stage.
        """
        # XXX improve the filter to handle categories
        stage_osv = self.pool.get('anytracker.stage')
        ticket_pool = self.pool.get('anytracker.ticket')
        project_id = ticket_pool.browse(cr, uid, context.get('active_id')).project_id
        if not project_id:
            return [], []
        method = project_id.method_id
        if not method:
            return [], []
        stage_ids = stage_osv.search(cr, uid, [('method_id', '=', method.id)], context=context)
        stage_names = stage_osv.name_get(cr, access_rights_uid, stage_ids, context=context)
        return stage_names, dict([(i, False) for i in ids])  # all unfolded

    def stage_previous(self, cr, uid, ids, context=None):
        """move the ticket to the previous stage
        """
        stage_pool = self.pool.get('anytracker.stage')
        for ticket in self.browse(cr, uid, ids, context):
            method = ticket.project_id.method_id
            if not method:
                raise osv.except_osv(_('Warning !'), _('No method defined in the project.'))
            stage_id = ticket.stage_id.id
            stage_ids = stage_pool.search(cr, uid, [('method_id', '=', method.id)])
            if stage_id == stage_ids[0]:  # first stage
                next_stage = False
            elif stage_id not in stage_ids:  # no stage
                continue
            else:
                next_stage = stage_ids[stage_ids.index(stage_id)-1]
            self.write(cr, uid, [ticket.id], {'stage_id': next_stage}, context)

    def stage_next(self, cr, uid, ids, context=None):
        """move the ticket to the next stage
        """
        stage_pool = self.pool.get('anytracker.stage')
        for ticket in self.browse(cr, uid, ids, context):
            method = ticket.project_id.method_id
            if not method:
                raise osv.except_osv(_('Warning !'), _('No method defined in the project.'))
            stage_id = ticket.stage_id.id
            stage_ids = stage_pool.search(cr, uid, [('method_id', '=', method.id)])
            if stage_id == stage_ids[-1]:  # last stage
                raise osv.except_osv(_('Warning !'), _("You're already in the last stage"))
            elif stage_id not in stage_ids:  # no stage
                next_stage = stage_ids[0]
            else:
                next_stage = stage_ids[stage_ids.index(stage_id)+1]
            self.write(cr, uid, [ticket.id], {'stage_id': next_stage}, context)

    def create(self, cr, uid, values, context=None):
        """select the default stage if parent is selected lately
        """
        if not values.get('stage_id') and values.get('parent_id'):
            method = self.browse(cr, uid, values.get('parent_id')).method_id
            values['stage_id'] = method.get_first_stage()[method.id]
        return super(Ticket, self).create(cr, uid, values, context)

    def write(self, cr, uid, ids, values, context=None):
        """set permission and children stages when writing stage_id
        """
        # check we can do this
        if values.get('stage_id'):
            # retrieving authorized groups for this stage
            groups_allowed = self.pool.get('anytracker.stage').read(
                cr, uid, values['stage_id'],
                ['groups_allowed'], load='_classic_write')['groups_allowed']
            if groups_allowed:
                # check if the user is in the right group to move the ticket to this stage
                browse_user = self.pool.get('res.users').browse(
                    cr, uid, uid)
                # retrieving user whole groups
                groups_ids = browse_user.groups_id
                parent_groups = None
                # loop through groups to only keep parent ones
                for group in groups_ids:
                    if not parent_groups:
                        parent_groups = set(groups_ids)
                    if not group.implied_ids:
                        continue
                    # remove imply group id from parent_groups
                    for imp_gr in group.implied_ids:
                        parent_groups.discard(imp_gr)
                user_groups = [ug.id for ug in parent_groups]
                if not set(user_groups).intersection(set(groups_allowed)) and uid != 1:
                    raise osv.except_osv('Operation forbidden',
                                         'You don\'t have the permission to move ticket '
                                         'to this stage')

        # save the previous progress
        if 'stage_id' in values:
            old_progress = dict([(t.id, t.stage_id.progress)
                                 for t in self.browse(cr, uid, ids, context)])

        res = super(Ticket, self).write(cr, uid, ids, values, context=context)

        # do nothing if we didn't modify the stage
        stage_id = values.get('stage_id', None)
        if not stage_id:
            return res

        if not hasattr(ids, '__iter__'):
            ids = [ids]
        for ticket in self.browse(cr, uid, ids, context):
            # check stage enforcements
            stage = self.pool.get('anytracker.stage').browse(cr, uid, stage_id, context)
            if not ticket.my_rating and stage.force_rating and not ticket.child_ids:
                raise osv.except_osv(_('Warning !'),
                                     _('You must rate the ticket "%s" to enter the "%s" stage'
                                       % (ticket.name, stage.name)))
            if ticket.my_rating.id in [i.id for i in (stage.forbidden_complexity_ids or [])]:
                    raise osv.except_osv(
                        _('Warning !'),
                        _('The ticket "%s" is rated "%s" so it cannot enter this stage'
                          % (ticket.name, ticket.my_rating.name)))
            # set all children as well
            super(Ticket, self).write(cr, uid, ticket.id, {'stage_id': stage_id}, context)
            self.write(cr, uid, [i.id for i in ticket.child_ids], {'stage_id': stage_id}, context)

        # Climb the tree from the ticket to the root
        # and recompute the progress of parents
        for ticket in self.browse(cr, uid, ids, context):
            ticket.write({'progress': ticket.stage_id.progress})
            parent = ticket.parent_id
            # loop up to the root
            while parent:
                child_ids = self.search(cr, uid, [('id', 'child_of', parent.id),
                                                  ('child_ids', '=', False),
                                                  ('id', '!=', parent.id)])
                progression = (ticket.stage_id.progress
                               - (old_progress[ticket.id]or 0.0)) / len(child_ids)
                new_progress = parent.progress + progression
                new_progress = 100.0 if new_progress > 100.0 else new_progress
                new_progress = 0.0 if new_progress < 0.0 else new_progress
                parent.write({'progress': new_progress})
                parent = parent.parent_id
        return res

        return super(Ticket, self).write(cr, uid, ids, values, context=context)

    def _default_stage(self, cr, uid, context):
        active_id = context.get('active_id')
        if not active_id:
            return False
        method = self.browse(cr, uid, context.get('active_id')).method_id
        return method.get_first_stage()[method.id]

    def recompute_progress(self, cr, uid, ids, context=None):
        """recompute the overall progress of the ticket, based on subtickets.
        And recompute sub-nodes as well
        """
        if not context:
            context = {}
        for ticket in self.browse(cr, uid, ids, context):
            if not ticket.child_ids:
                self.write(cr, uid, ticket.id, {'progress': ticket.stage_id.progress}, context)
            else:
                leaf_ids = self.search(cr, uid, [('id', 'child_of', ticket.id),
                                                 ('child_ids', '=', False),
                                                 ('id', '!=', ticket.id)])
                for leaf in self.browse(cr, uid, leaf_ids, context):
                    leaf.write({'progress': leaf.stage_id.progress})

            sub_node_ids = self.search(cr, uid, [('id', 'child_of', ticket.id),
                                                 ('child_ids', '!=', False),
                                                 ('id', '!=', ticket.id)])
            for node_id in [ticket.id] + sub_node_ids:
                leaf_ids = self.search(cr, uid, [('id', 'child_of', node_id),
                                                 ('child_ids', '=', False),
                                                 ('id', '!=', node_id)])
                progresses = self.read(cr, uid, leaf_ids, ['progress'])
                nb_tickets = len(progresses)
                if nb_tickets != 0:
                    progress = sum([t['progress'] or 0.0 for t in progresses]) / float(nb_tickets)
                else:
                    progress = ticket.stage_id.progress
                self.write(cr, uid, node_id, {'progress': progress}, context)
        return True

    def _constant_one(self, cr, uid, ids, *a, **kw):
        return dict((i, 1) for i in ids)

    _columns = {
        'stage_id': fields.many2one(
            'anytracker.stage',
            'Stage',
            select=True,
            domain="[('method_id','=',method_id)]"),
        'progress': fields.float(
            'Progress',
            select=True,
            group_operator="avg"),
        # this field can be used to count tickets if the only available operation
        # on them is to sum field values (shameless hack for charts)
        'constant_one': fields.function(
            _constant_one, type='integer',
            obj='anytracker.ticket',
            string='Constant one',
            store=True,
            invisible=True),
    }

    _group_by_full = {
        'stage_id': _read_group_stage_ids,
    }

    _defaults = {
        'stage_id': _default_stage,
        'progress': 0.0,
    }


class Method(osv.Model):
    _inherit = 'anytracker.method'
    _columns = {
        'stage_ids': fields.one2many(
            'anytracker.stage',
            'method_id',
            'Stages',
            help="The stages associated to this method"),
    }

    def get_first_stage(self, cr, uid, ids, context=None):
        """ Return the id of the first stage of a method"""
        res = {}
        for method in self.browse(cr, uid, ids, context):
            stages = [(s.progress, s.id) for s in method.stage_ids]
            res[method.id] = sorted(stages)[0][1] if len(stages) else False
        return res
