from osv import fields, osv
from tools.translate import _

class Stage(osv.osv):
    """Add progress value to the stage
    """
    _inherit = 'anytracker.stage'
    _columns = {
        'progress': fields.float('Progress', help='Progress value of the ticket reaching this stage'),
    }

class Ticket(osv.osv):
    """Add progress functionnality to tickets
    """
    _inherit = 'anytracker.ticket'

    def _get_weighted_progress(self, cr, uid, ids, field_name, args, context=None):
        """get the overall progress of the ticket and number of tickets, based on subtickets.
        It should return a tuple with a float between 0 and 1, and the total number of subtickets.
        Progress is defined by the mean of percentages defined in stages.
        """
        if not context: context = {}
        res = {}
        for ticket in self.browse(cr, uid, ids, context):
            child_ids = self.search(cr, uid, [('id', 'child_of', ticket.id),
                                              ('child_ids', '=', False),
                                              ('id', '!=', ticket.id)])
            progresses = self.read(cr, uid, child_ids, ['progress'])
            nb_tickets = len(progresses)
            if nb_tickets != 0:
                progress, nb_tickets = sum([t['progress'] or 0.0 for t in progresses]) / float(nb_tickets), nb_tickets
            else:
                progress, nb_tickets = ticket.stage_id.progress, 1
            res[ticket.id] = progress, nb_tickets
        return res

    def _get_progress(self, cr, uid, ids, field_name, args, context=None):
        """ keep only the progress, skip the number
        """
        res = self._get_weighted_progress(cr, uid, ids, field_name, args, context)
        for i in res:
            res[i] = res[i][0]
        return res

    _columns = { 
        'progress': fields.function(_get_progress,
                                    method=True,
                                    type='float',
                                    string="Progress"),
     }
