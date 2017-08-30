import otree.api
import random, numpy, itertools, json, copy
from matching_algorithms import *


author = 'Ciara Mulcahy'

doc = """
This is a multi-period slot machine game with 3 [var] players.
Each round, every player selects whether to 
remain at the same slot machine, switch slot machines, or quit the game entirely. 
"""


class Constants(otree.api.BaseConstants):
    name_in_url = 'SlotMachines'
    num_groups = 3      # change this to handle super-grouping
    timeout_seconds = 100

    instructions_template = 'matchingAlg/Instructions.html'
    # reference the (matching algorithm and payout generation) file here

    # Can manipulate the variables below
    players_per_group = 4
    num_rounds = 10

    num_sm = players_per_group + num_rounds
    potSlots = list(range(1, num_sm+1))

    payout_max = 20
    sd_payoffs = 5
    init_quit_pay = 7*num_rounds
    dec_quit_pay = 7


class Subsession(otree.api.BaseSubsession):
    def creating_session(self):
        if self.round_number == 1:
            self.group_randomly()     # assign players to groups randomly, with fixed ids

            for g in self.get_groups():
                for p in g.get_players():
                    p.participant.vars['role'] = p.id_in_group - 1
                    p.role()

            # need to reevaluate this - 0-20 associated with [times switched away from, times accessed] this payout

            # make session-global payoff_dict for selfish alg [times switched away from, times accessed] this payout
            self.session.vars['payoff_dict'] = {}
            init_visit_list = [0,0]        # [times switched away from, times accessed] this payout
            for pay_amt in range(Constants.payout_max + 1):
                self.session.vars['payoff_dict'][pay_amt] = init_visit_list

            # assign payoffs to player role numbers across groups
            self.session.vars['combinations'] = {}
            for super_group in range(1, Constants.num_groups + 1):
                self.session.vars['combinations'][super_group] = correlated_payoffs(Constants.num_sm, Constants.players_per_group)   # new implementation

            # assign matching algorithm to each group
            groups = self.get_groups()
            alg = itertools.cycle(['fair', 'self'])
            count = 2
            for g in groups:
                g.alg = next(alg)
                g.super_group = count // 2
                player_scribe = g.get_player_by_id(1)
                player_scribe.participant.vars["super_group"] = count//2
                count += 1

                # initially activate players instances
                for p in g.get_players():
                    p.participant.vars['slotMachinesPrev'] = set()
                    p.participant.vars['statusActive'] = True

                g.switching = json.dumps(list(range(Constants.players_per_group)))   # all 'switch' 1st round
                g.remaining = json.dumps([])
                player_scribe.participant.vars['occupied'] = set()  # no slot machines are occupied yet

                # Maybe put initial assignments by the matching alg file right here
                g.make_options()
                g.match_pay()

        else:
            self.group_like_round(1)    # keep same grouping

            # inherit attributes of previous round
            for g in self.get_groups():

                prev_round = self.round_number-1
                g.alg = g.in_round(prev_round).alg  # group keeps the same matching alg [treatment]

                g.super_group = g.in_round(prev_round).super_group


class Group(otree.api.BaseGroup):
    # Group means treatment group(but players are interacting), so fair or selfish matching algorithm applied
    super_group = otree.api.models.PositiveIntegerField()       # associated with a set of pot payoffs
    alg = otree.api.models.CharField()
    switching = otree.api.models.CharField()
    remaining = otree.api.models.CharField()

    def before_next_round(self):
        player_scribe = self.get_player_by_role(0)
        occ = player_scribe.participant.vars['occupied']
        prev_round = self.round_number - 1

        this_switch = []
        this_remain = []
        for p in self.get_players():
            p.mean_payoff_current = p.participant.vars['meanPayoutCurrent']
            if p.participant.vars['statusActive']:
                if p.in_round(prev_round).offer_accepted == 3:  # quit
                    p.participant.vars['statusActive'] = False
                    occ.remove(p.participant.vars['slotMachineCurrent'])  # sm no longer occupied
                    p.participant.payoff += p.quit_payoff()

                elif p.in_round(prev_round).offer_accepted == 2:  # switch
                    occ.remove(p.participant.vars['slotMachineCurrent'])   # sm no longer occupied
                    this_switch.append(p.id_in_group)
                    self.session.vars['payoff_dict'][p.mean_payoff_current][0] += 1   # switching from

                elif p.in_round(prev_round).offer_accepted == 1:  # remain
                    this_remain.append(p.id_in_group)
                    p.current_slot_machine_id = json.dumps(p.participant.vars['slotMachineCurrent'])

        self.switching = json.dumps(this_switch)
        self.remaining = json.dumps(this_remain)
        self.make_options()
        self.match_pay()

    def make_options(self):
        player_scribe = self.get_player_by_role(0)
        switching = json.loads(self.switching)
        remaining = json.loads(self.remaining)

        opts = {}
        for p_id in switching:
            p = self.get_player_by_role(p_id)
            p.make_payoff_dict()
            opts[p_id] = p.participant.vars['payouts']

            # debug
            '''
            for sm_id,pay_amt in p.participant.vars['payouts'].items():
                if pay_amt < 0 or pay_amt >20:
                    raise ValueError()
            '''

        for p_id in remaining:
            p = self.get_player_by_id(p_id)
            sm_current = json.loads(p.current_slot_machine_id)
            temp_dict = {sm_current: p.payoff_current}
            opts[p_id] = temp_dict

        player_scribe.participant.vars["options"] = opts


    def match_pay(self):
        player_scribe = self.get_player_by_role(0)
        groups_occupied = player_scribe.participant.vars['occupied']

        if self.alg == 'fair':
            p_ids, sm_ids, pay_amts = fair_matching(player_scribe.participant.vars['options'], Constants.num_sm, Constants.players_per_group)    # p_ids not necessary

        elif self.alg == 'self':
            prob = copy.deepcopy(self.session.vars['payoff_dict'])
            defaults = initialize_probs()
            for key in prob:    # replace list with probabilities
                if prob[key][-1] != 0:
                    prob[key] = (defaults[key] * 5 + (prob[key][0]/prob[key][-1])* prob[key][-1])/(5 + prob[key][-1])    # factor in the initial pseudoprobs by weighting
                else:
                    prob[key] = defaults[key]
            p_ids, sm_ids, pay_amts = self_matching(player_scribe.participant.vars['options'], Constants.num_sm, Constants.players_per_group, prob)
        else:
            raise ValueError()

        # raise ValueError("Just checking %r" % (pay_amts))

        for i in range(len(sm_ids)):
            player = self.get_player_by_role(p_ids[i])  # only look at active players
            if player.participant.vars['statusActive']:
                slot_mach_id = sm_ids[i]
                player.participant.vars['slotMachineCurrent'] = slot_mach_id
                player.current_slot_machine_id = json.dumps(int(slot_mach_id))

                player.payoff_current = pay_amts[i]

                self.session.vars['payoff_dict'][pay_amts[i]][-1] += 1  # update times accessed in payoff_dict

                groups_occupied.add(slot_mach_id)  # note that sm is now occupied
                player.participant.vars['slotMachinesPrev'].add(slot_mach_id)  # note that player cannot return to this sm

                # payout the payoffs
                player.payoff = pay_amts[i]



class Player(otree.api.BasePlayer):
    current_slot_machine_id = otree.api.models.CharField()
    payoff_current = otree.api.models.IntegerField()

    def role(self):
        if self.round_number == 1:
            return self.id_in_group - 1
        return self.participant.vars['role']

    # saving this dictionary like this may cause problems
    sm_options = otree.api.models.CharField(initial="NA")

    # for Player.offer_accepted variable, 1 = return, 2 = switch, 3 = quit game
    offer_accepted = otree.api.models.PositiveIntegerField(
        choices=[
            [1, 'Return to same slot machine'],
            [2, 'Switch slot machines'],
            [3, 'Quit this game'],
        ], widget=otree.api.widgets.RadioSelect()
    )
    # record the slot machine ids with which the player has matched as self.participant.vars['slotMachinesPrev']

    # make payout dictionary of the player - algorithm file may make this inappropriate
    def make_payoff_dict(self):
        player_scribe = self.group.get_player_by_role(0)
        groups_occupied = player_scribe.participant.vars['occupied']
        p_id = self.participant.vars['role']
        poten_combos = copy.deepcopy(self.session.vars['combinations'][self.group.super_group][p_id])   # indexing the correlated payoffs list, returns a dict sm --> pay_amt

        prev_slot_mach = self.participant.vars['slotMachinesPrev']
        sm_id_options = list(poten_combos.keys())
        for sm_id in sm_id_options:
            if sm_id in groups_occupied or sm_id in prev_slot_mach:  # check for occupied or previous sm's
                del poten_combos[sm_id]
                continue

        # associate payouts with player p at different slot machine options
        self.participant.vars['payouts'] = poten_combos
        self.sm_options = json.dumps(poten_combos)      # this might cause problems



    # linear decrease in quitting payout across rounds
    def quit_payoff(self):
        return Constants.init_quit_pay - (self.round_number - 1)* Constants.dec_quit_pay
