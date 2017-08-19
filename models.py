import otree.api
import random, numpy, itertools, json, copy
from json import JSONEncoder, JSONDecoder
import pickle


author = 'Ciara Mulcahy'

doc = """
This is a multi-period slot machine game with 3 [var] players.
Each round, every player selects whether to 
remain at the same slot machine, switch slot machines, or quit the game entirely. 
"""


class Constants(otree.api.BaseConstants):
    name_in_url = 'SlotMachines'
    num_groups = 3
    timeout_seconds = 100

    instructions_template = 'matchingAlg/Instructions.html'\

    # Can manipulate the variables below
    players_per_group = 3
    num_rounds = 3
    num_sm = players_per_group + num_rounds
    potSlots = list(range(1, num_sm+1))

    payout_max = 20
    sd_payoffs = 5
    init_quit_pay = 7*num_rounds
    dec_quit_pay = 8


class Subsession(otree.api.BaseSubsession):
    def creating_session(self):
        if self.round_number == 1:
            self.group_randomly()     # assign players to groups randomly, with fixed ids

            for g in self.get_groups():
                for p in g.get_players():
                    p.participant.vars['role'] = p.id_in_group
                    p.role()

            # make session-global payoff_dict to store data for selfish alg
            self.session.vars['payoff_dict'] = {}
            init_visit_list = [0,0]        # [times switched away from, times accessed] this payout
            for _ in range(Constants.num_sm):
                pay_amt = int(numpy.random.pareto(.5))
                # pay_amt = random.randint(0, Constants.payout_max)
                self.session.vars['payoff_dict'][pay_amt] = init_visit_list
                # this needs to be fixed to ensure that enough payouts are assigned and even distribution etc

            # assign payoffs to player ids across groups
            self.session.vars['combinations'] = {}
            for p_id in range(1, Constants.players_per_group + 1):
                # regenerate the potential payouts between players, should not affect session.vars
                player_pay = self.session.vars['payoff_dict'].keys()
                self.session.vars['combinations'][p_id] = {}
                for sm_id in range(1, Constants.num_sm + 1):
                    pay = int(numpy.random.choice(list(player_pay), replace=False))
                    self.session.vars['combinations'][p_id][sm_id] = pay

            # assign matching algorithm to each group
            groups = self.get_groups()
            alg = itertools.cycle(['fair', 'self', 'rand'])
            for g in groups:
                g.alg = next(alg)
                # initially activate players instances
                for p in g.get_players():
                    p.participant.vars['slotMachinesPrev'] = set()
                    p.participant.vars['statusActive'] = True

                player_scribe = g.get_player_by_id(1)
                g.switching = json.dumps(list(range(1, Constants.players_per_group + 1)))   # all 'switch' 1st round
                player_scribe.participant.vars['occupied'] = set()  # no slot machines are occupied yet

                g.reassign()

        else:
            self.group_like_round(1)    # keep same grouping

            # inherit attributes of previous round
            for g in self.get_groups():

                prev_round = self.round_number-1
                g.alg = g.in_round(prev_round).alg  # group keeps the same matching alg [treatment]
                g.switching = []


class Group(otree.api.BaseGroup):
    # Group means treatment group(but players are interacting), so fair or selfish matching algorithm applied
    alg = otree.api.models.CharField()
    switching = otree.api.models.CharField()

    def before_next_round(self):
        player_scribe = self.get_player_by_role(1)
        occ = player_scribe.participant.vars['occupied']
        prev_round = self.round_number - 1

        this_switch = list(json.loads(self.switching))
        for p in self.get_players():
            p.mean_payoff_current = p.participant.vars['meanPayoutCurrent']
            if p.participant.vars['statusActive']:
                if p.in_round(prev_round).offer_accepted == 3:  # quit
                    p.participant.vars['statusActive'] = False
                    occ.remove(p.participant.vars['slotMachineCurrent'])  # sm no longer occupied
                    p.quit_payoff()
                elif p.in_round(prev_round).offer_accepted == 2:  # switch
                    occ.remove(p.participant.vars['slotMachineCurrent'])   # sm no longer occupied
                    this_switch.append(p.id_in_group)
                    # will handle slot machine reassignment and payout in reassign function below [greedy alg]
                    self.session.vars['payoff_dict'][p.mean_payoff_current][0] += 1
                elif p.in_round(prev_round).offer_accepted == 1:  # remain
                    p.payoff = numpy.random.normal(loc=p.mean_payoff_current, scale=Constants.sd_payoffs)
                    self.session.vars['payoff_dict'][p.mean_payoff_current][-1] += 1  # fix these counts later
                    p.current_slot_machine_id = json.dumps(p.participant.vars['slotMachineCurrent'])

        self.switching = json.dumps(this_switch)
        self.reassign()

    # Handle slot machines for checking players' options
    def reassign(self):          # use for initial matching and switching cases
        switching = json.loads(self.switching)
        player_scribe = self.get_player_by_role(1)
        groups_occupied = player_scribe.participant.vars['occupied']

        random.shuffle(switching)   # shuffle order of switching player ids - unfair if p1 always assigned first
        for p_id in switching:
            p = self.get_player_by_id(p_id)
            p.make_payoff_dict()
            players_pot_payouts = p.participant.vars['payouts']

            # reassign slot machines - add sm to occupied and change players's value for currentSM
            if self.alg == 'fair':
                # need to make probabilistic, but deterministic for now
                newSMpay = max(players_pot_payouts.values())
            elif self.alg == 'rand':
                newSMpay = random.choice(list(players_pot_payouts.values()))
            elif self.alg == 'self':
                newSMpay = random.choice(list(players_pot_payouts.values()))    # change this later
            else:
                raise ValueError()

            slot_mach_id = list(players_pot_payouts.keys())[list(players_pot_payouts.values()).index(newSMpay)]

            p.participant.vars['slotMachineCurrent'] = slot_mach_id  # assign sm to player
            p.current_slot_machine_id = json.dumps(slot_mach_id)
            p.participant.vars['meanPayoutCurrent'] = newSMpay
            p.mean_payoff_current = newSMpay

            groups_occupied.add(slot_mach_id)        # note that sm is now occupied
            p.participant.vars['slotMachinesPrev'].add(slot_mach_id)     # note that player cannot return to this sm

            # payout the payoffs
            # p.payoff = numpy.random.normal(loc=newSMpay, scale=Constants.sd_payoffs)
            p.payoff = int(newSMpay)


class Player(otree.api.BasePlayer):
    current_slot_machine_id = otree.api.models.CharField()
    mean_payoff_current = otree.api.models.PositiveIntegerField()

    def role(self):
        if self.round_number == 1:
            return self.id_in_group
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

    # make payout dictionary of the player
    def make_payoff_dict(self):
        player_scribe = self.group.get_player_by_role(1)
        groups_occupied = player_scribe.participant.vars['occupied']
        p_id = self.participant.vars['role']
        poten_combos = copy.deepcopy(self.session.vars['combinations'][p_id])

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
        if self.round_number == 1:
            self.participant.payoff = Constants.init_quit_pay
        else:
            self.participant.payoff += Constants.init_quit_pay - (self.round_number - 1)* Constants.dec_quit_pay
