from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
# import below for defining custom models: match to save the player-slot machine-payoff combinations
from otree.db.models import Model, ForeignKey
from django.contrib.postgres.fields import ArrayField
import random, numpy, itertools


author = 'Ciara Mulcahy'

doc = """
This is a multi-period slot machine game with 3 [var] players.
Each round, every player selects whether to 
remain at the same slot machine, switch slot machines, or quit the game entirely. 
"""


class Constants(BaseConstants):
    name_in_url = 'SlotMachines'
    num_groups = 3

    instructions_template = 'matchingAlg/Instructions.html'\

    # Can manipulate the variables below
    players_per_group = 3
    num_rounds = 2
    num_sm = players_per_group + num_rounds
    potSlots = list(range(1, num_sm+1))

    payout_max = 100
    sd_payoffs = 20
    init_quit_pay = 150
    dec_quit_pay = 45


class Subsession(BaseSubsession):

    def before_session_starts(self):
        rounds_remaining = Constants.num_rounds - self.round_number

        if self.round_number == 1:
            self.group_randomly(fixed_id_in_group=True)     # assign players to groups

            # make session-global payoff_dict to store data for selfish alg
            self.session.vars['payoff_dict'] = {}
            init_visit_list = [0,0]        # [times switched away from, times received this payout]
            for _ in range(Constants.num_sm):
                self.session.vars['payoff_dict'][c(numpy.random.randint(low=0, high=100))] = init_visit_list

            # assign payoffs to player ids in a group
            for p_id in range(1, Constants.players_per_group + 1):
                # regenerate the potential payouts between players, should not affect session.vars
                player_pay = self.session.vars['payoff_dict'].keys()

                for sm_id in range(1, Constants.num_sm + 1):
                    # make an instance of Match with the given player id in group and slot machine

                    pay = numpy.random.choice(list(player_pay), replace=False)

                    for g in self.get_groups():
                        g.make_player_sm_combo(p_id, sm_id, pay)

            # assign matching algorithm to each group
            groups = self.get_groups()
            alg = itertools.cycle(['fair', 'self', 'rand'])
            for g in groups:
                g.alg = next(alg)

            # cycle through groups to initially assign players to slot machines
            for g in groups:
                for p in g.get_players():
                    p.participant.vars['slotMachinesPrev'] = set()

                data_store_player = g.get_player_by_id(1)
                data_store_player.participant.vars['switching'] = list(range(1, Constants.players_per_group + 1))

                g.reassign()

        else:
            self.group_like_round(1)    # keep same grouping

            # inherit attributes of previous round
            for g in self.get_groups():
                prev_round = self.round_number-1
                g.alg = g.in_round(self.round_number-1).alg
                prev_combination_set = g.in_round(prev_round).combination_set.all()
                for combo in prev_combination_set:
                    g.combination_set.add(combo)
                for p in g.get_players():
                    p.slotMachineCurrent = p.in_round(prev_round).slotMachineCurrent
                    p.mean_payoff_current = p.in_round(prev_round).mean_payoff_current
                    p.statusActive = p.in_round(prev_round).statusActive

                # work around to save group variables globally
                data_store_player = g.get_player_by_id(1)
                data_store_player.participant.vars['switching'] = []    # reset the list of switching players
                g.before_next_round()


class Group(BaseGroup):
    # Group means treatment group(but players are interacting), so fair or selfish matching algorithm applied
    alg = models.CharField()

    def make_player_sm_combo(self, p_id, sm_id, pay):  # make the match instances for the group
        if not self.combination_set:
            combination = self.combination_set.create(player_id_in_group = p_id, slot_machine_id = sm_id, mean_payoff = pay)
            combination.save()  # save to DB
        else:
            self.combination_set.add(Combination(player_id_in_group = p_id, slot_machine_id = sm_id, mean_payoff = pay))

    # Handle slot machines for checking players' options

    def reassign(self):          # use for initial matching and switching cases
        # reassign slot machines and provide payout for those switching

        # work around to Store group's variable lists and sets
        data_store_player = self.get_player_by_id(1)

        switching = data_store_player.participant.vars['switching']
        if len(switching) ==0:
            raise ValueError()        # raise error to debug, really would call 'pass'

        data_store_player.participant.vars['groupSMavailable'] = []
        group_sm_available = data_store_player.participant.vars['groupSMavailable']

        data_store_player.participant.vars['occupied'] = set()
        occupied = data_store_player.participant.vars['occupied']

        for sm_id in Constants.potSlots:
            if sm_id not in occupied:
                group_sm_available.append(sm_id)  # unoccupied slot machines in this group

        random.shuffle(switching)   # shuffle order of switching player ids - unfair if p1 always assigned first

        for p_id in switching:
            p = self.get_player_by_id(p_id)

            # find available slot machines
            p.participant.vars['playerSMavailable'] = []
            for sm_id in group_sm_available:
                if sm_id not in p.participant.vars['slotMachinesPrev']:
                    if sm_id not in data_store_player.participant.vars['occupied']:      # recheck for assignments of other switching players
                        p.participant.vars['playerSMavailable'].append(sm_id)

            # associate payouts with player p at different slot machine options
            p.participant.vars['payouts'] = {}
            payouts = p.participant.vars['payouts']

            for sm_id in p.participant.vars['playerSMavailable']:
                sm_current = self.combination_set.filter(slot_machine_id = sm_id, player_id_in_group = p_id)[0]
                pay_amt = sm_current.mean_payoff
                payouts[pay_amt] = sm_id

            # reassign slot machines - add sm to occupied and change p2's value for currentSM
            if self.alg == 'fair':
                # need to make probabilistic, but deterministic for now
                newSMpay = max(payouts.keys())
            elif self.alg == 'rand':
                newSMpay = random.choice(list(payouts.keys()))
            elif self.alg == 'self':
                newSMpay = random.choice(list(payouts.keys()))    # change this later
            else:
                raise ValueError()

            slot_mach_id = payouts[newSMpay]
            p.slotMachineCurrent = slot_mach_id  # assign sm to player
            p.mean_payoff_current = newSMpay
            occupied.add(slot_mach_id)        # note that sm is now occupied
            p.participant.vars['slotMachinesPrev'].add(slot_mach_id)     # note that player cannot return to this sm

            # payout the payoffs
            #p.payoff = c(numpy.random.normal(loc=newSMpay, scale=Constants.sd_payoffs))
            p.payoff = newSMpay

    def before_next_round(self):

        data_store_player = self.get_player_by_id(1)
        occupied = data_store_player.participant.vars['occupied']
        switching = data_store_player.participant.vars['switching']

        for p in self.get_players():
            if p.statusActive:
                if p.offer_accepted == 3:
                    p.statusActive = False
                    occupied.remove(p.slotMachineCurrent) # sm no longer occupied
                    p.quit_payoff()
                elif p.offer_accepted == 2:
                    occupied.remove(p.slotMachineCurrent)
                    switching.append(p.id_in_group)
                    # will handle slot machine reassignment and payout in reassign funct below [greedy alg]
                    self.session.vars['payoff_dict'][p.mean_payoff_current][0] += 1
                elif p.offer_accepted == 1:
                    p.payoff = numpy.random.normal(loc = p.mean_payoff_current, scale = Constants.sd_payoffs)
                    self.session.vars['payoff_dict'][p.mean_payoff_current][-1] += 1      # fix these counts later

        self.reassign()


class Combination(Model):
    # Combination means a potential combination of a slot machine and a player

    mean_payoff = models.PositiveIntegerField()
    slot_machine_id = models.PositiveIntegerField()
    player_id_in_group = models.PositiveIntegerField()

    group = ForeignKey(Group)


class Player(BasePlayer):
    statusActive = models.BooleanField(initial = True)

    slotMachineCurrent = models.PositiveIntegerField()
    mean_payoff_current = models.PositiveIntegerField()

    payoff = models.CurrencyField()

    # for Player.offer_accepted variable, 1 = return, 2 = switch, 3 = quit game
    offer_accepted = models.PositiveIntegerField(
        choices=[
            [1, 'Return to same slot machine'],
            [2, 'Switch slot machines'],
            [3, 'Quit this game'],
        ], initial = 2
    )

    # record the slot machine ids with which the player has matched as self.participant.vars['slotMachinesPrev']

    # linear decrease in quitting payout across rounds
    def quit_payoff(self):
        if Subsession.round_number == 1:
            self.participant.payoff = Constants.init_quit_pay
        else:
            self.participant.payoff += Constants.init_quit_pay - (Subsession.round_number - 1)* Constants.dec_quit_pay

